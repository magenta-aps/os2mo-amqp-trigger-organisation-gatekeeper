# SPDX-FileCopyrightText: Magenta ApS <https://magenta.dk>
# SPDX-License-Identifier: MPL-2.0

from uuid import UUID

import structlog
from fastapi import Request
from fastapi import Response
from fastapi.routing import APIRouter
from fastramqpi.raclients.graph.client import PersistentGraphQLClient
from fastramqpi.raclients.modelclient.mo import ModelClient
from gql import gql
from more_itertools import one
from starlette.status import HTTP_204_NO_CONTENT
from starlette.status import HTTP_503_SERVICE_UNAVAILABLE

from .async_utils import gather_with_concurrency
from .calculate import get_org_units_with_no_hierarchy
from .calculate import update_line_management

logger = structlog.stdlib.get_logger()

router = APIRouter()


@router.get("/")
async def index() -> dict[str, str]:
    return {"name": "orggatekeeper"}


@router.post("/trigger/all", status_code=202)
async def update_all_org_units(request: Request) -> None:  # pragma: no cover
    """Call update_line_management on all org units."""
    context = request.app.state.context
    gql_client = context["gql_client"]
    query = gql("query OrgUnitUUIDQuery { org_units { objects { uuid } } }")
    result = await gql_client.execute(query)

    org_unit_uuids = [UUID(o["uuid"]) for o in result["org_units"]["objects"]]
    logger.info("Manually triggered recalculation", uuids=org_unit_uuids)
    org_unit_tasks = [
        update_line_management(**context, uuid=uuid) for uuid in org_unit_uuids
    ]
    await gather_with_concurrency(5, *org_unit_tasks)  # type: ignore


@router.post(
    "/trigger/{uuid}",
)
async def update_org_unit(request: Request, uuid: UUID) -> dict[str, str]:
    """Call update_line_management on the provided org unit."""
    context = request.app.state.context
    logger.info("Manually triggered recalculation", uuids=[uuid])
    await update_line_management(**context, uuid=uuid)
    return {"status": "OK"}


@router.post(
    "/ensure-no-unset",
)
async def ensure_no_unset(request: Request) -> dict[str, str]:
    """Check that all orgunits belong to a org_unit_hierarchy."""
    context = request.app.state.context
    logger.info("Manually triggered check for unset org_unit_hierarchy")
    res = await get_org_units_with_no_hierarchy(context["gql_client"])
    if len(res) == 0:
        logger.info("No orgunits with unset org_unit_hierarchy found")
        return {"status": "OK"}

    logger.error("Unset org_unit_hierarchy.", uuids=res)
    tasks = [update_line_management(**context, uuid=uuid) for uuid in res]
    await gather_with_concurrency(5, *tasks)  # type: ignore

    return {"status": f"Updated {len(res)} orgunits"}


@router.get("/health/live", status_code=HTTP_204_NO_CONTENT)
async def liveness() -> None:
    """Endpoint to be used as a liveness probe for Kubernetes."""
    return None


@router.get(
    "/health/ready",
    status_code=HTTP_204_NO_CONTENT,
    responses={
        "204": {"description": "Ready"},
        "503": {"description": "Not ready"},
    },
)
async def readiness(request: Request, response: Response) -> Response:
    """Endpoint to be used as a readiness probe for Kubernetes."""
    context = request.app.state.context

    response.status_code = HTTP_204_NO_CONTENT

    healthchecks = {}
    try:
        # Check AMQP connection
        healthchecks["AMQP"] = context["amqp_system"].healthcheck()
        # Check GraphQL connection (gql_client)
        healthchecks["GraphQL"] = await _healthcheck_gql(context["gql_client"])
        # Check Service API connection (model_client)
        healthchecks["Service API"] = await _healthcheck_model_client(
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


async def _healthcheck_gql(gql_client: PersistentGraphQLClient) -> bool:
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


async def _healthcheck_model_client(model_client: ModelClient) -> bool:
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
