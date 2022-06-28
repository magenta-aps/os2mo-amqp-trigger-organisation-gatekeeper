# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
"""Event handling."""
from functools import partial
from operator import itemgetter
from typing import Any
from typing import Protocol
from uuid import UUID

import structlog
from fastapi import APIRouter
from fastapi import FastAPI
from fastapi import Query
from fastapi import Request
from gql import gql
from prometheus_client import Counter
from ramqp.mo import MORouter
from ramqp.mo.models import ObjectType
from ramqp.mo.models import PayloadType
from ramqp.mo.models import RequestType
from ramqp.mo.models import ServiceType

from .calculate import update_line_management
from .config import get_settings
from .utils import gather_with_concurrency
from fastramqpi.main import FastRAMQPI


logger = structlog.get_logger()
update_counter = Counter(
    "orggatekeeper_changes",
    "Number of updates made",
    ["updated"],
)
fastapi_router = APIRouter()
amqp_router = MORouter()


# pylint: disable=too-few-public-methods
class GenUpdateLineManagement(Protocol):
    """Typed function signature of gen_update_line_management return value."""

    async def __call__(self, uuid: UUID) -> bool:
        ...


def gen_update_line_management(context: dict) -> GenUpdateLineManagement:
    """Seed update_line_management with arguments from context.

    Args:
        context: dictionary to extract arguments from.

    Returns:
        update_line_management that only takes an UUID.
    """

    seeded_func = partial(
        update_line_management,
        gql_session=context["graphql_session"],
        model_client=context["model_client"],
        settings=context["user_context"]["settings"],
    )
    return lambda uuid: seeded_func(uuid=uuid)


@fastapi_router.post(
    "/trigger/all",
)
async def update_all_org_units(request: Request) -> dict[str, str]:
    """Call update_line_management on all org units."""
    context: dict[str, Any] = request.app.state.context
    gql_session = context["graphql_session"]

    query = gql("query OrgUnitUUIDQuery { org_units { uuid } }")
    result = await gql_session.execute(query)
    org_unit_uuids = map(UUID, map(itemgetter("uuid"), result["org_units"]))
    org_unit_tasks = map(gen_update_line_management(context), org_unit_uuids)
    await gather_with_concurrency(5, *org_unit_tasks)
    return {"status": "OK"}


@fastapi_router.post(
    "/trigger/{uuid}",
)
async def update_org_unit(
    request: Request,
    uuid: UUID = Query(..., description="UUID of the organisation unit to recalculate"),
) -> dict[str, str]:
    """Call update_line_management on the provided org unit."""
    context: dict[str, Any] = request.app.state.context
    await gen_update_line_management(context)(uuid)
    return {"status": "OK"}


@amqp_router.register(
    ServiceType.ORG_UNIT, ObjectType.ASSOCIATION, RequestType.WILDCARD
)
@amqp_router.register(ServiceType.ORG_UNIT, ObjectType.ENGAGEMENT, RequestType.WILDCARD)
@amqp_router.register(ServiceType.ORG_UNIT, ObjectType.ORG_UNIT, RequestType.WILDCARD)
async def organisation_gatekeeper_callback(
    context: dict,
    payload: PayloadType,
) -> None:
    """Updates line management information.

    Args:
        context: The execution context.
        payload: The message payload.

    Returns:
        None
    """
    changed = await gen_update_line_management(context)(uuid=payload.uuid)
    update_counter.labels(updated=changed).inc()


def create_fastramqpi(**kwargs: Any) -> FastRAMQPI:
    """FastRAMQPI factory.

    Starts the metrics server, then listens to AMQP messages forever.

    Args:
        kwargs: Settings-overrides.

    Returns:
        FastRAMQPI system.
    """
    settings = get_settings(**kwargs)
    fastramqpi = FastRAMQPI(
        application_name="orggatekeeper", settings=settings.fastramqpi
    )
    fastramqpi.add_context(settings=settings)

    # Add our routers
    amqpsystem = fastramqpi.get_amqpsystem()
    # amqpsystem.include_router(amqp_router)
    amqpsystem.router.registry.update(amqp_router.registry)

    app = fastramqpi.get_app()
    app.include_router(fastapi_router)
    return fastramqpi


def create_app(**kwargs: Any) -> FastAPI:
    """FastAPI application factory.

    Args:
        kwargs: Settings-overrides.

    Returns:
        FastAPI ASGI application.
    """
    fastramqpi = create_fastramqpi(**kwargs)
    return fastramqpi.get_app()
