# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
"""Event handling."""
from asyncio import gather
from asyncio import Semaphore
from functools import partial
from operator import itemgetter
from typing import Any
from typing import Awaitable
from typing import Callable
from typing import Tuple
from typing import TypeVar
from uuid import UUID

import structlog
from fastapi import FastAPI
from fastapi import Query
from fastapi import Response
from gql import gql
from more_itertools import one
from prometheus_client import Counter
from prometheus_client import Info
from prometheus_fastapi_instrumentator import Instrumentator
from raclients.graph.client import PersistentGraphQLClient
from raclients.modelclient.mo import ModelClient
from ramqp.mo_models import MORoutingKey
from ramqp.mo_models import ObjectType
from ramqp.mo_models import PayloadType
from ramqp.mo_models import RequestType
from ramqp.mo_models import ServiceType
from ramqp.moqp import MOAMQPSystem
from starlette.status import HTTP_204_NO_CONTENT
from starlette.status import HTTP_503_SERVICE_UNAVAILABLE

from .calculate import update_line_management
from .config import get_settings
from .config import Settings
from .mo import fetch_org_uuid

logger = structlog.get_logger()
T = TypeVar("T")


update_counter = Counter(
    "orggatekeeper_changes",
    "Number of updates made",
    ["updated"],
)
build_information = Info("build_information", "Build information")


def update_build_information(version: str, build_hash: str) -> None:
    """Update build information.

    Args:
        version: The version to set.
        build_hash: The build hash to set.

    Returns:
        None.
    """
    build_information.info(
        {
            "version": version,
            "hash": build_hash,
        }
    )


async def healthcheck_gql(gql_client: PersistentGraphQLClient) -> bool:
    """Check that our GraphQL connection is healthy.

    Args:
        gql_client: The GraphQL client to check health of.

    Returns:
        Whether the client is healthy or not.
    """
    query = gql(
        """
        query HealthcheckQuery {
            org {
                uuid
            }
        }
        """
    )
    try:
        result = await gql_client.execute(query)
        if result["org"]["uuid"]:
            return True
    except Exception:  # pylint: disable=broad-except
        logger.exception("Exception occured during GraphQL healthcheck")
    return False


async def healthcheck_model_client(model_client: ModelClient) -> bool:
    """Check that our ModelClient connection is healthy.

    Args:
        model_client: The MO Model client to check health of.

    Returns:
        Whether the client is healthy or not.
    """
    try:
        response = await model_client.get("/service/o/")
        result = response.json()
        if one(result)["uuid"]:
            return True
    except Exception:  # pylint: disable=broad-except
        logger.exception("Exception occured during GraphQL healthcheck")
    return False


async def organisation_gatekeeper_callback(
    seeded_update_line_management: Callable[[UUID], Awaitable[bool]],
    mo_routing_key: MORoutingKey,
    payload: PayloadType,
) -> None:
    """Updates line management information.

    Args:
        gql_client: GraphQL client.
        model_client: MO model client.
        settings: Integration settings module.
        mo_routing_key: The message routing key.
        payload: The message payload.

    Returns:
        None
    """
    logger.debug(
        "Message received",
        service_type=mo_routing_key.service_type,
        object_type=mo_routing_key.object_type,
        request_type=mo_routing_key.request_type,
        payload=payload,
    )
    changed = await seeded_update_line_management(payload.uuid)
    update_counter.labels(updated=changed).inc()


def construct_clients(
    settings: Settings,
) -> Tuple[PersistentGraphQLClient, ModelClient]:
    """Construct clients froms settings.

    Args:
        settings: Integration settings module.

    Returns:
        Tuple with PersistentGraphQLClient and ModelClient.
    """
    gql_client = PersistentGraphQLClient(
        url=settings.mo_url + "/graphql",
        client_id=settings.client_id,
        client_secret=settings.client_secret.get_secret_value(),
        auth_server=settings.auth_server,
        auth_realm=settings.auth_realm,
        execute_timeout=settings.graphql_timeout,
        httpx_client_kwargs={"timeout": settings.graphql_timeout},
    )
    model_client = ModelClient(
        base_url=settings.mo_url,
        client_id=settings.client_id,
        client_secret=settings.client_secret.get_secret_value(),
        auth_server=settings.auth_server,
        auth_realm=settings.auth_realm,
    )
    return gql_client, model_client


def configure_logging(settings: Settings) -> None:
    """Setup our logging.

    Args:
        settings: Integration settings module.

    Returns:
        None
    """
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(settings.log_level.value)
    )


async def gather_with_concurrency(parallel: int, *tasks: Awaitable[T]) -> list[T]:
    """Asyncio gather, but with limited concurrency.

    Args:
        parallel: The number of concurrent tasks being executed.
        tasks: List of tasks to execute.

    Returns:
        List of return values from awaiting the tasks.
    """
    semaphore = Semaphore(parallel)

    async def semaphore_task(task: Awaitable[T]) -> T:
        async with semaphore:
            return await task

    return await gather(*map(semaphore_task, tasks))


def construct_context() -> dict[str, Any]:
    """Construct request context."""
    return {}


def create_app(  # pylint: disable=too-many-statements
    *args: Any, **kwargs: Any
) -> FastAPI:
    """FastAPI application factory.

    Starts the metrics server, then listens to AMQP messages forever.

    Returns:
        None
    """
    settings = get_settings(*args, **kwargs)
    configure_logging(settings)

    app = FastAPI()

    logger.info("Starting metrics server")
    update_build_information(
        version=settings.commit_tag, build_hash=settings.commit_sha
    )
    if settings.expose_metrics:
        Instrumentator().instrument(app).expose(app)

    context = construct_context()

    @app.on_event("startup")
    async def startup_amqp_consumer() -> None:
        logger.info("Settings up clients")
        gql_client, model_client = construct_clients(settings)
        context["gql_client"] = gql_client
        context["model_client"] = model_client

        # Get organisation UUID
        org_uuid = await fetch_org_uuid(gql_client)

        logger.info("Seeding line management function")
        seeded_update_line_management = partial(
            update_line_management, gql_client, model_client, settings, org_uuid
        )
        context["seeded_update_line_management"] = seeded_update_line_management

        logger.info("Settings up AMQP system")
        callback = partial(
            organisation_gatekeeper_callback, seeded_update_line_management
        )

        object_types = [
            ObjectType.ASSOCIATION,
            ObjectType.ENGAGEMENT,
            ObjectType.ORG_UNIT,
            ObjectType.IT,
        ]
        amqp_system = MOAMQPSystem()
        for object_type in object_types:
            amqp_system.register(
                ServiceType.ORG_UNIT, object_type, RequestType.WILDCARD
            )(callback)
        context["amqp_system"] = amqp_system

        logger.info("Starting AMQP system")
        await amqp_system.start(queue_prefix=settings.queue_prefix)

    @app.on_event("shutdown")
    async def stop_amqp_consumer() -> None:
        amqp_system = context["amqp_system"]
        await amqp_system.stop()

        gql_client = context["gql_client"]
        await gql_client.aclose()

        model_client = context["model_client"]
        await model_client.aclose()

    @app.get("/")
    async def index() -> dict[str, str]:
        return {"name": "orggatekeeper"}

    @app.post(
        "/trigger/all",
    )
    async def update_all_org_units() -> dict[str, str]:
        """Call update_line_management on all org units."""
        gql_client = context["gql_client"]
        query = gql("query OrgUnitUUIDQuery { org_units { uuid } }")
        result = await gql_client.execute(query)
        org_unit_uuids = map(UUID, map(itemgetter("uuid"), result["org_units"]))
        org_unit_tasks = map(context["seeded_update_line_management"], org_unit_uuids)
        await gather_with_concurrency(5, *org_unit_tasks)
        return {"status": "OK"}

    @app.post(
        "/trigger/{uuid}",
    )
    async def update_org_unit(
        uuid: UUID = Query(
            ..., description="UUID of the organisation unit to recalculate"
        )
    ) -> dict[str, str]:
        """Call update_line_management on the provided org unit."""
        await context["seeded_update_line_management"](uuid)
        return {"status": "OK"}

    @app.get("/health/live", status_code=HTTP_204_NO_CONTENT)
    async def liveness() -> None:
        """Endpoint to be used as a liveness probe for Kubernetes."""
        return None

    @app.get(
        "/health/ready",
        status_code=HTTP_204_NO_CONTENT,
        responses={
            "204": {"description": "Ready"},
            "503": {"description": "Not ready"},
        },
    )
    async def readiness(response: Response) -> Response:
        """Endpoint to be used as a readiness probe for Kubernetes."""
        response.status_code = HTTP_204_NO_CONTENT

        healthchecks = {}
        try:
            # Check AMQP connection
            healthchecks["AMQP"] = context["amqp_system"].healthcheck()
            # Check GraphQL connection (gql_client)
            healthchecks["GraphQL"] = await healthcheck_gql(context["gql_client"])
            # Check Service API connection (model_client)
            healthchecks["Service API"] = await healthcheck_model_client(
                context["model_client"]
            )
        except Exception:  # pylint: disable=broad-except
            logger.exception("Exception occured during readiness probe")
            response.status_code = HTTP_503_SERVICE_UNAVAILABLE

        for name, ready in healthchecks.items():
            if not ready:
                logger.warn(f"{name} is not ready")

        if not all(healthchecks.values()):
            response.status_code = HTTP_503_SERVICE_UNAVAILABLE

        return response

    return app
