# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
"""Update logic."""
import datetime
import re
from asyncio import gather
from typing import Any
from uuid import UUID

import structlog
from gql import gql
from more_itertools import one
from raclients.graph.client import PersistentGraphQLClient
from raclients.modelclient.mo import ModelClient
from ramodels.mo import Validity
from ramodels.mo._shared import OrgUnitHierarchy
from ramqp.depends import Context
from ramqp.depends import RateLimit
from ramqp.mo import MORouter
from ramqp.mo import PayloadType
from ramqp.mo import PayloadUUID

from .config import Settings
from .mo import fetch_org_unit
from .mo import get_class_uuid
from .mo import get_it_system_uuid

router = MORouter()

logger = structlog.get_logger()
ny_regex = re.compile(r"NY\d-niveau")


async def should_hide(
    gql_client: PersistentGraphQLClient,
    uuid: UUID,
    enable_hide_logic: bool,
    hidden: set[UUID],
) -> bool:
    """Determine whether the organisation unit should be hidden.

    Args:
        gql_client: The GraphQL client to run our queries on.
        org_unit: The organisation unit object.
        hidden: User-keys of organisation units to hide (all children included).

    Returns:
        Whether the organisation unit should be hidden.
    """
    if not enable_hide_logic:
        return False
    if uuid in hidden:
        return True
    return await below_uuid(gql_client, uuid=uuid, uuids=hidden)


async def check_org_unit_line_management(
    gql_client: PersistentGraphQLClient,
    uuid: UUID,
    org_unit: dict,
    line_management_top_level_uuid: set[UUID],
) -> bool:
    """Checks if a given org_unit passes the requirements to be in line management"""
    if not org_unit.get("org_unit_level"):
        logger.debug("Found no org_unit_level, assuming not in line-org", uuid=uuid)
        return False
    unit_level_user_key = org_unit["org_unit_level"]["user_key"]
    # Part of line management if unit_level_user_key matches regex
    # Or if it is "Afdelings-niveau"
    is_ny_level = ny_regex.fullmatch(unit_level_user_key) is not None
    is_department_level = unit_level_user_key == "Afdelings-niveau"
    if not is_ny_level and not is_department_level:
        return False
    # Also it needs to have people attached to be line managent
    # TODO: Check owners, leaders, it?
    has_engagements = bool(org_unit["engagements"])
    has_associations = bool(org_unit["associations"])
    if not has_engagements and not has_associations:
        return False
    # AND it needs to be below an orgunit that is explicitly line management
    if not await below_uuid(
        gql_client, uuid=uuid, uuids=line_management_top_level_uuid
    ):
        return False
    # If all above checks passes it is line management.
    return True


async def is_line_management(
    gql_client: PersistentGraphQLClient,
    uuid: UUID,
    line_management_top_level_uuid: set[UUID],
    hidden_engagement_types: list[str],
) -> bool:
    """Determine whether the organisation unit is part of line management.

    Args:
        gql_client: The GraphQL client to run our queries on.
        uuid: UUID of the organisation unit.
        line_management_top_level_uuid: set of user_keys which are always
        line_management

    Returns:
        Whether the organisation unit should be part of line management.
    """
    if uuid in line_management_top_level_uuid:
        return True

    query = gql("""
        query OrgUnitQuery($uuids: [UUID!]) {
            org_units(uuids: $uuids) {
                objects {
                    org_unit_level {
                        user_key
                    }
                    engagements {
                        uuid
                        engagement_type {
                            name
                        }
                    }
                    associations {
                        uuid
                    }
                    children {
                        uuid
                    }
                }
            }
        }
        """)

    result = await gql_client.execute(query, {"uuids": [str(uuid)]})
    obj = one(one(result["org_units"])["objects"])
    if hidden_engagement_types:
        obj["engagements"] = [
            e
            for e in obj["engagements"]
            if e["engagement_type"]["name"] not in hidden_engagement_types
        ]
    # Check this unit according to the rules for line-management
    if await check_org_unit_line_management(
        gql_client=gql_client,
        uuid=uuid,
        org_unit=obj,
        line_management_top_level_uuid=line_management_top_level_uuid,
    ):
        return True
    # If the above check fails we need to check below this org_unit to see if
    # an org_unit below this unit is line-management. Then we need to mark this one
    # as line management too in order for the frontend to show the whole tree.
    for child in obj["children"]:
        if await is_line_management(
            gql_client=gql_client,
            uuid=child["uuid"],
            line_management_top_level_uuid=line_management_top_level_uuid,
            hidden_engagement_types=hidden_engagement_types,
        ):
            return True
    return False


async def is_self_owned(
    gql_client: PersistentGraphQLClient, uuid: UUID, check_it_system_name: str
) -> bool:
    """Determine whether the organisation unit should be marked as self-owned.
    A unit is marked as self-owned if it is not in line-management but has an it-account
    in the it-system with user_key set in check_it_system_name

    Args:
        gql_client: The GraphQL client to run our queries on.
        uuid: UUID of the organisation unit.
        check_it_system_name: user_key of the it-system to check

    Returns:
        Whether the organisation unit should be marked as self-owned
    """
    check_it_system_uuid = await get_it_system_uuid(
        gql_client=gql_client, user_key=check_it_system_name
    )

    query = gql("""
        query OrgUnitQuery($uuids: [UUID!]) {
            org_units(uuids: $uuids) {
                objects {
                    itusers {
                        itsystem_uuid
                    }
                }
            }
        }
        """)
    result = await gql_client.execute(query, {"uuids": [str(uuid)]})
    obj = one(one(result["org_units"])["objects"])

    return any(
        UUID(it.get("itsystem_uuid")) == check_it_system_uuid for it in obj["itusers"]
    )


async def below_uuid(
    gql_client: PersistentGraphQLClient, uuid: UUID, uuids: set[UUID]
) -> bool:
    """Determine whether the organisation unit is below one where user_key
    is in the given list

    Args:
        gql_client: The GraphQL client to run our queries on.
        uuid: uuid of an organisation unit.
        uuids: uuids of organisation units to check parentship on.

    Returns:
        Whether the organisation unit has a parent with uuid in uuids.
    """
    if not uuids:
        logger.debug("below_uuid called with empty uuid list")
        return False

    query = gql("""
        query ParentQuery($uuids: [UUID!]) {
            org_units(uuids: $uuids) {
                objects {
                    parent { uuid }
                }
            }
        }
        """)
    result = await gql_client.execute(query, {"uuids": [str(uuid)]})
    obj = one(one(result["org_units"])["objects"])

    parent = obj["parent"]

    if not parent:
        # top level org_unit
        return False

    if UUID(parent["uuid"]) in uuids:
        return True

    return await below_uuid(gql_client, uuid=parent["uuid"], uuids=uuids)


async def update_line_management(
    gql_client: PersistentGraphQLClient,
    model_client: ModelClient,
    settings: Settings,
    org_uuid: UUID,
    uuid: UUID,
    **_: Any,
) -> bool:
    """Update line management information for the provided organisation unit.

    An organisation unit is part of line management iff:
    * The SD unit-level is NY{x}-niveau or
    * The SD unit-level is Afdelings-niveau and people are attached to it.

    Additionally, this function also hides organisation units iff:
    * Their user-key is contained within hidden_user_key or a child of it.

    Args:
        gql_client: The GraphQL client to run queries on.
        model_client: The MO Model client to modify MO with.
        settings: The integration settings module.
        org_uuid: The UUID of the LoRa organisation
        uuid: UUID of the organisation unit to recalculate.

    Returns:
        Whether an update was made.
    """
    # Determine the desired org_unit_hierarchy class uuid
    new_org_unit_hierarchy: OrgUnitHierarchy | None = None
    # if the orgunit uuid is in settings.hidden or it is below one that is
    # it should be hidden
    if await should_hide(
        gql_client=gql_client,
        uuid=uuid,
        enable_hide_logic=settings.enable_hide_logic,
        hidden=settings.hidden,
    ):
        logger.info("Organisation Unit needs to be hidden", uuid=uuid)
        hidden_uuid = await get_class_uuid(
            gql_client,
            settings.hidden_uuid,
            settings.hidden_user_key,
        )
        new_org_unit_hierarchy = OrgUnitHierarchy(uuid=hidden_uuid)
    elif await is_line_management(
        gql_client,
        uuid,
        settings.line_management_top_level_uuids,
        settings.hidden_engagement_types,
    ):
        logger.info("Organisation Unit needs to be in line management", uuid=uuid)
        line_management_uuid = await get_class_uuid(
            gql_client,
            settings.line_management_uuid,
            settings.line_management_user_key,
        )
        new_org_unit_hierarchy = OrgUnitHierarchy(uuid=line_management_uuid)
    elif settings.self_owned_it_system_check and await is_self_owned(
        gql_client, uuid, settings.self_owned_it_system_check
    ):
        logger.info("Organisation Unit needs to marked as self-owned", uuid=uuid)
        self_owned_uuid = await get_class_uuid(
            gql_client,
            settings.self_owned_uuid,
            settings.self_owned_user_key,
        )
        new_org_unit_hierarchy = OrgUnitHierarchy(uuid=self_owned_uuid)
    else:
        logger.info("Organisation Unit needs to marked as outside hierarchy", uuid=uuid)
        na_uuid = await get_class_uuid(
            gql_client,
            None,
            "NA",
        )
        new_org_unit_hierarchy = OrgUnitHierarchy(uuid=na_uuid)

    # Fetch the current object and see if we need to update it
    org_unit = await fetch_org_unit(gql_client, uuid)
    if org_unit.org_unit_hierarchy == new_org_unit_hierarchy:
        logger.debug("Not updating org_unit_hierarchy, already good", uuid=uuid)
        return False

    # Prepare the updated object for writing
    # TODO: we will have a problem, if new_org_unit_hierarchy is None
    assert org_unit.parent is not None
    org_unit = org_unit.copy(
        update={
            "org_unit_hierarchy": new_org_unit_hierarchy,
            # When parent is set, MO will try to move the org unit which is
            # not allowed by MO for a root org unit. Therefor we set the parent
            # to None in the update operation if the parent of the org unit is
            # the LoRa organisation
            "parent": org_unit.parent if org_unit.parent.uuid != org_uuid else None,
            "validity": Validity(from_date=datetime.datetime.now().date()),
        }
    )

    if settings.dry_run:
        logger.info("dry-run: Would have send edit payload", org_unit=org_unit)
        return True
    logger.info(
        "Editing organisation unit",
        uuid=uuid,
        new_org_unit_hierarchy=new_org_unit_hierarchy,
    )
    logger.debug("Sending ModelClient edit request", org_unit=org_unit)
    response = await model_client.edit([org_unit])
    logger.debug("ModelClient response", response=response)
    if org_unit.parent is not None:
        # Check if parent org_unit needs to be updated.
        await update_line_management(
            gql_client, model_client, settings, org_uuid, org_unit.parent.uuid
        )
    return True


async def get_org_units_with_no_hierarchy(
    gql_client: PersistentGraphQLClient,
) -> list[UUID]:
    """Get all org_units that have no org_unit_hierarchy set.

    Args:
        gql_client: The GraphQL client to use.

    Returns:
        List of uuids for org_units with no org_unit_hierarchy.
    """
    query = gql("""
        query GetOrgUnitHierarchy {
          org_units {
            uuid
            objects {
              org_unit_hierarchy
            }
          }
        }
        """)
    result = await gql_client.execute(query)
    missing = [
        ou["uuid"]
        for ou in result["org_units"]
        if one(ou["objects"])["org_unit_hierarchy"] is None
    ]
    return missing


async def get_orgunit_from_engagement(
    gql_client: PersistentGraphQLClient, engagement_uuid: UUID
) -> set[UUID]:
    """Get org_unit uuid from user uuid

    Args:
        gql_client: The GraphQL client to use.
        engagement_uuid: UUID of an engagement

    Returns:
        Set of org_unit uuids connected to the engagement


    """
    query = gql("""
        query GetOrgUnit($uuids: [UUID!]) {
            engagements(uuids: $uuids, to_date: null, from_date: null) {
                objects {
                    org_unit_uuid
                }
            }
        }
        """)
    result = await gql_client.execute(query, {"uuids": str(engagement_uuid)})

    objects = one(result["engagements"])["objects"]

    return {UUID(e["org_unit_uuid"]) for e in objects}


async def get_orgunit_from_association(
    gql_client: PersistentGraphQLClient, associations_uuid: UUID
) -> set[UUID]:
    """Get org_unit uuid from user uuid

    Args:
        gql_client: The GraphQL client to use.
        associations_uuid: UUID of an engagement

    Returns:
        Set of org_unit uuids connected to the associations


    """
    query = gql("""
        query GetOrgUnit($uuids: [UUID!]) {
            associations(uuids: $uuids, to_date: null, from_date: null) {
                objects {
                    org_unit_uuid
                }
            }
        }
        """)
    result = await gql_client.execute(query, {"uuids": str(associations_uuid)})

    objects = one(result["associations"])["objects"]

    return {UUID(e["org_unit_uuid"]) for e in objects}


async def update(context: Context, org_units: set[UUID]) -> None:
    """Call update_line_management for each uuid in the given set"""
    await gather(*[update_line_management(**context, uuid=uuid) for uuid in org_units])


@router.register("org_unit.org_unit.*")
@router.register("org_unit.it.*")
async def org_unit_callback(
    context: Context, payload: PayloadType, _: RateLimit
) -> None:
    """Callback to check org_unit_hierarchy.

    Listens to changes on org_units and it-accounts on org_units.
    """
    org_units = {payload.uuid}
    logger.info("Changes to org_unit or its it-accounts", org_unit=org_units)
    try:
        await update(context, org_units)
    except ValueError:
        logger.info("No org_unit found. Skipping", payload=payload)


@router.register("association")
async def association_callback(
    context: Context, payload: PayloadUUID, _: RateLimit
) -> None:
    """Callback to check org_unit_hierarchy on changes to associations."""
    try:
        org_units = await get_orgunit_from_association(context["gql_client"], payload)
        logger.info("Changes to association. Checking org_units", org_unit=org_units)
        await update(context, org_units)
    except ValueError:
        logger.debug("Association not found", payload=payload)
        return


@router.register("engagement")
async def engagement_callback(
    context: Context, payload: PayloadUUID, _: RateLimit
) -> None:
    """Callback to check org_unit_hierarchy on changes to engagements."""
    try:
        org_units = await get_orgunit_from_engagement(context["gql_client"], payload)
        logger.info("Changes to engagement. Checking org_units", org_unit=org_units)
        await update(context, org_units)
    except ValueError:
        logger.debug("Engagement not found", payload=payload)
        return
