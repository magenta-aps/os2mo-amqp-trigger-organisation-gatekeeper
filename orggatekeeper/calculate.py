# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
"""Update logic."""
import datetime
import re
from uuid import UUID

import structlog
from gql import gql
from more_itertools import one
from raclients.graph.client import PersistentGraphQLClient
from raclients.modelclient.mo import ModelClient
from ramodels.mo import Validity
from ramodels.mo._shared import OrgUnitHierarchy

from .config import Settings
from .mo import fetch_org_unit
from .mo import get_class_uuid
from .mo import get_it_system_uuid

logger = structlog.get_logger()
ny_regex = re.compile(r"NY\d-niveau")


async def is_line_management(gql_client: PersistentGraphQLClient, uuid: UUID) -> bool:
    """Determine whether the organisation unit is part of line management.

    Args:
        gql_client: The GraphQL client to run our queries on.
        uuid: UUID of the organisation unit.

    Returns:
        Whether the organisation unit should be part of line management.
    """
    query = gql(
        """
        query OrgUnitQuery($uuids: [UUID!]) {
            org_units(uuids: $uuids) {
                objects {
                    org_unit_level {
                        user_key
                    }
                    engagements {
                        uuid
                    }
                    associations {
                        uuid
                    }
                }
            }
        }
        """
    )
    result = await gql_client.execute(query, {"uuids": [str(uuid)]})
    obj = one(one(result["org_units"])["objects"])
    logger.debug("GraphQL obj", obj=obj)

    if not obj["org_unit_level"]:
        logger.debug(f"Found no org_unit_level on {uuid=}, assuming not in line-org")
        return False

    unit_level_user_key = obj["org_unit_level"]["user_key"]

    # Part of line management if userkey matches regex
    if ny_regex.fullmatch(unit_level_user_key) is not None:
        return True
    # Or if it is "Afdelings-niveau" and it has people attached
    if unit_level_user_key == "Afdelings-niveau":
        # TODO: Check owners, leaders, it?
        if len(obj["engagements"]) > 0:
            return True
        if len(obj["associations"]) > 0:
            return True
    return False


async def is_self_owned(
    gql_client: PersistentGraphQLClient, uuid: UUID, check_it_system_name: str | None
) -> bool:
    """Determine whether the organisation unit should be marked as self-owned.

    Args:
        gql_client: The GraphQL client to run our queries on.
        uuid: UUID of the organisation unit.

    Returns:
        Whether the organisation unit should be marked as self-owned
    """
    if check_it_system_name is None:
        return False

    check_it_system_uuid = await get_it_system_uuid(
        gql_client=gql_client, user_key=check_it_system_name
    )

    query = gql(
        """
        query OrgUnitQuery($uuids: [UUID!]) {
            org_units(uuids: $uuids) {
                objects {
                    itusers {
                        itsystem_uuid
                    }
                }
            }
        }
        """
    )
    result = await gql_client.execute(query, {"uuids": [str(uuid)]})
    obj = one(one(result["org_units"])["objects"])
    logger.debug("GraphQL obj", obj=obj)
    return any(
        UUID(it.get("itsystem_uuid")) == check_it_system_uuid for it in obj["itusers"]
    )


async def should_hide(
    gql_client: PersistentGraphQLClient, uuid: UUID, hidden: list[str]
) -> bool:
    """Determine whether the organisation unit should be hidden.

    Args:
        gql_client: The GraphQL client to run our queries on.
        org_unit: The organisation unit object.
        hidden: User-keys of organisation units to hide (all children included).

    Returns:
        Whether the organisation unit should be hidden.
    """
    # TODO: Should we really just be updating the top-most parent itself?
    # TODO answer: probably not as this leads(?) to HTTP status 500 errors
    # (see Redmine 46148 #82)
    if not hidden:
        logger.debug("should_hide called with empty hidden list")
        return False

    query = gql(
        """
        query ParentQuery($uuids: [UUID!]) {
            org_units(uuids: $uuids) {
                objects {
                    user_key
                    parent_uuid
                }
            }
        }
        """
    )
    result = await gql_client.execute(query, {"uuids": [str(uuid)]})
    obj = one(one(result["org_units"])["objects"])
    logger.debug("GraphQL obj", obj=obj)

    if obj["user_key"] in hidden:
        return True
    if obj["parent_uuid"] is not None:
        return await should_hide(gql_client, obj["parent_uuid"], hidden)
    return False


async def update_line_management(
    gql_client: PersistentGraphQLClient,
    model_client: ModelClient,
    settings: Settings,
    org_uuid: UUID,
    uuid: UUID,
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
    if settings.enable_hide_logic and await should_hide(
        gql_client, uuid, settings.hidden
    ):
        logger.debug("Organisation Unit needs to be hidden", uuid=uuid)
        hidden_uuid = await get_class_uuid(
            gql_client,
            settings.hidden_uuid,
            settings.hidden_user_key,
        )
        new_org_unit_hierarchy = OrgUnitHierarchy(uuid=hidden_uuid)
    elif await is_line_management(gql_client, uuid):
        logger.debug("Organisation Unit needs to be in line management", uuid=uuid)
        line_management_uuid = await get_class_uuid(
            gql_client,
            settings.line_management_uuid,
            settings.line_management_user_key,
        )
        new_org_unit_hierarchy = OrgUnitHierarchy(uuid=line_management_uuid)
    elif await is_self_owned(gql_client, uuid, settings.self_owned_it_system_check):
        logger.debug("Organisation Unit needs to marked as self-owned", uuid=uuid)
        self_owned_uuid = await get_class_uuid(
            gql_client,
            settings.self_owned_uuid,
            settings.self_owned_user_key,
        )
        new_org_unit_hierarchy = OrgUnitHierarchy(uuid=self_owned_uuid)
    else:
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

    logger.debug("Sending ModelClient edit request", org_unit=org_unit)
    response = await model_client.edit([org_unit])
    logger.debug("ModelClient response", response=response)
    return True
