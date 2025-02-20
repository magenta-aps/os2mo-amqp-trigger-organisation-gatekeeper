# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
"""Event handling."""

from asyncio import Semaphore
from asyncio import gather
from collections.abc import AsyncIterator
from collections.abc import Awaitable
from contextlib import asynccontextmanager
from typing import Any
from typing import TypeVar
from uuid import UUID

import sentry_sdk
import structlog
from fastapi import APIRouter
from fastapi import BackgroundTasks
from fastapi import FastAPI
from fastapi import Response
from fastramqpi.depends import LegacyGraphQLSession
from fastramqpi.depends import LegacyModelClient
from fastramqpi.main import FastRAMQPI
from fastramqpi.raclients.graph.client import PersistentGraphQLClient
from fastramqpi.raclients.modelclient.mo import ModelClient
from fastramqpi.ramqp.depends import Context
from gql import gql
from more_itertools import one
from starlette.status import HTTP_204_NO_CONTENT
from starlette.status import HTTP_503_SERVICE_UNAVAILABLE

from .calculate import get_org_units_with_no_hierarchy
from .calculate import router
from .calculate import update_line_management
from .config import get_settings
from .depends import OrgUuid
from .depends import Settings
from .mo import fetch_org_uuid

logger = structlog.get_logger()
T = TypeVar("T")
fastapi_router = APIRouter()


async def healthcheck_gql(gql_client: PersistentGraphQLClient) -> bool:
    """Check that our GraphQL connection is healthy.

    Args:
        gql_client: The GraphQL client to check health of.

    Returns:
        Whether the client is healthy or not.
    """
    query = gql("""
        query HealthcheckQuery {
            org {
                uuid
            }
        }
        """)
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
        response = await model_client.async_httpx_client.get("/service/o/")
        result = response.json()
        if one(result)["uuid"]:
            return True
    except Exception:  # pylint: disable=broad-except
        logger.exception("Exception occured during GraphQL healthcheck")
    return False


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


@asynccontextmanager
async def set_org_uuid_context(
    fastramqpi: FastRAMQPI,
) -> AsyncIterator[None]:
    """Looks up organisation uuid and saves it in context for later use"""
    context = fastramqpi.get_context()
    logger.info("Fetching org_uuid")
    org_uuid = await fetch_org_uuid(context["legacy_graphql_session"])
    fastramqpi.add_context(org_uuid=org_uuid)
    yield


def create_app(  # pylint: disable=too-many-statements
    *args: Any, **kwargs: Any
) -> FastAPI:
    """FastAPI application factory.

    Starts the metrics server, then listens to AMQP messages forever.

    Returns:
        None
    """
    settings = get_settings(*args, **kwargs)

    if settings.sentry_dsn:  # pragma: no cover
        sentry_sdk.init(dsn=settings.sentry_dsn)

    fastramqpi = FastRAMQPI(
        application_name="os2mo-organisation-gatekeeper",
        settings=settings.fastramqpi,
        graphql_version=22,
    )
    fastramqpi.add_context(settings=settings)
    fastramqpi.add_context(org_uuid=None)
    # Add our AMQP router(s)
    amqpsystem = fastramqpi.get_amqpsystem()
    amqpsystem.router.registry.update(router.registry)

    # Add our FastAPI router(s)
    app = fastramqpi.get_app()
    app.include_router(fastapi_router)

    logger.info("Before lifespan")
    logger.info(fastramqpi.get_context())
    fastramqpi.add_lifespan_manager(set_org_uuid_context(fastramqpi), priority=1101)

    return app


@fastapi_router.get("/")
async def index() -> dict[str, str]:
    """Identify integration"""
    return {"name": "orggatekeeper"}


@fastapi_router.post("/trigger/all", status_code=202)
async def update_all_org_units(
    model_client: LegacyModelClient,
    gql_client: LegacyGraphQLSession,
    settings: Settings,
    org_uuid: OrgUuid,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """Call update_line_management on all org units."""

    query = gql("query OrgUnitUUIDQuery { org_units { objects { uuid } } }")
    result = await gql_client.execute(query)

    org_unit_uuids = [UUID(o["uuid"]) for o in result["org_units"]["objects"]]
    logger.info("Manually triggered recalculation", uuids=org_unit_uuids)

    org_unit_tasks = [
        update_line_management(
            gql_client=gql_client,
            model_client=model_client,
            settings=settings,
            org_uuid=org_uuid,
            uuid=uuid,
        )
        for uuid in org_unit_uuids
    ]
    background_tasks.add_task(
        gather_with_concurrency,
        5,
        *org_unit_tasks,  # type: ignore
    )
    return {"status": "Background job triggered"}


@fastapi_router.post(
    "/trigger/{uuid}",
)
async def update_org_unit(context: Context, uuid: UUID) -> dict[str, str]:
    """Call update_line_management on the provided org unit."""
    logger.info("Manually triggered recalculation", uuids=[uuid])
    await update_line_management(**context, uuid=uuid)
    return {"status": "OK"}


@fastapi_router.post(
    "/ensure-no-unset",
)
async def ensure_no_unset(context: Context) -> dict[str, str]:
    """Check that all orgunits belong to a org_unit_hierarchy."""
    logger.info("Manually triggered check for unset org_unit_hierarchy")
    res = await get_org_units_with_no_hierarchy(context["gql_client"])
    if len(res) == 0:
        logger.info("No orgunits with unset org_unit_hierarchy found")
        return {"status": "OK"}

    logger.error("Unset org_unit_hierarchy.", uuids=res)
    tasks = [update_line_management(**context, uuid=uuid) for uuid in res]
    await gather_with_concurrency(5, *tasks)  # type: ignore

    return {"status": f"Updated {len(res)} orgunits"}


@fastapi_router.get("/health/live", status_code=HTTP_204_NO_CONTENT)
async def liveness() -> None:
    """Endpoint to be used as a liveness probe for Kubernetes."""
    return None


@fastapi_router.get(
    "/health/ready",
    status_code=HTTP_204_NO_CONTENT,
    responses={
        "204": {"description": "Ready"},
        "503": {"description": "Not ready"},
    },
)
async def readiness(context: Context, response: Response) -> Response:
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
