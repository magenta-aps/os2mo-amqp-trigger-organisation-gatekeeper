# SPDX-FileCopyrightText: Magenta ApS <https://magenta.dk>
# SPDX-License-Identifier: MPL-2.0

from uuid import UUID

import structlog
from fastapi import Request
from fastapi.routing import APIRouter
from gql import gql

from .async_utils import gather_with_concurrency
from .calculate import get_org_units_with_no_hierarchy
from .calculate import update_line_management

logger = structlog.stdlib.get_logger()

router = APIRouter()


@router.post("/trigger/all", status_code=202)
async def update_all_org_units(request: Request) -> None:  # pragma: no cover
    """Call update_line_management on all org units."""
    context = request.app.state.context
    gql_client = context["legacy_graphql_session"]
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
    res = await get_org_units_with_no_hierarchy(context["legacy_graphql_session"])
    if len(res) == 0:
        logger.info("No orgunits with unset org_unit_hierarchy found")
        return {"status": "OK"}

    logger.error("Unset org_unit_hierarchy.", uuids=res)
    tasks = [update_line_management(**context, uuid=uuid) for uuid in res]
    await gather_with_concurrency(5, *tasks)  # type: ignore

    return {"status": f"Updated {len(res)} orgunits"}
