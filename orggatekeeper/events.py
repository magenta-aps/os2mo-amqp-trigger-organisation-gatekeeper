# SPDX-FileCopyrightText: Magenta ApS <https://magenta.dk>
# SPDX-License-Identifier: MPL-2.0

import structlog
from fastramqpi.ramqp.depends import Context
from fastramqpi.ramqp.depends import RateLimit
from fastramqpi.ramqp.mo import MORouter
from fastramqpi.ramqp.mo import PayloadUUID

from . import calculate
from .calculate import get_orgunit_from_association
from .calculate import get_orgunit_from_engagement
from .calculate import get_orgunit_from_ituser
from .calculate import update

router = MORouter()

logger = structlog.get_logger()


@router.register("org_unit")
async def org_unit_handler(context: Context, uuid: PayloadUUID, _: RateLimit) -> None:
    """Callback to check org_unit_hierarchy.

    Listens to changes on org_units and it-accounts on org_units.
    """

    logger.info("Changes to org_unit or its it-accounts", org_unit=uuid)
    await calculate.update_line_management(**context, uuid=uuid)


@router.register("ituser")
async def ituser_callback(context: Context, payload: PayloadUUID, _: RateLimit) -> None:
    """Callback to check org_unit_hierarchy on changes to associations."""
    try:
        org_units = await get_orgunit_from_ituser(
            context["legacy_graphql_session"], payload
        )
    except ValueError:
        logger.debug("Association not found", payload=payload)
        return
    logger.info("Changes to association. Checking org_units", org_unit=org_units)
    await update(context, org_units)


@router.register("association")
async def association_callback(
    context: Context, payload: PayloadUUID, _: RateLimit
) -> None:
    """Callback to check org_unit_hierarchy on changes to associations."""
    try:
        org_units = await get_orgunit_from_association(
            context["legacy_graphql_session"], payload
        )
    except ValueError:
        logger.debug("Association not found", payload=payload)
        return
    logger.info("Changes to association. Checking org_units", org_unit=org_units)
    await update(context, org_units)


@router.register("engagement")
async def engagement_callback(
    context: Context, payload: PayloadUUID, _: RateLimit
) -> None:
    """Callback to check org_unit_hierarchy on changes to engagements."""
    try:
        org_units = await get_orgunit_from_engagement(
            context["legacy_graphql_session"], payload
        )
    except ValueError:
        logger.debug("Engagement not found", payload=payload)
        return
    logger.info("Changes to engagement. Checking org_units", org_unit=org_units)
    await update(context, org_units)
