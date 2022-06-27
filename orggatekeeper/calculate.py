# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
"""Update logic."""
import datetime
import re
from operator import itemgetter
from typing import Optional
from uuid import UUID

import structlog
from gql import gql
from more_itertools import one
from raclients.graph.client import PersistentGraphQLClient
from raclients.modelclient.mo import ModelClient
from ramodels.mo import OrganisationUnit
from ramodels.mo import Validity

from .config import Settings

logger = structlog.get_logger()


async def fetch_org_unit_hierarchy_uuid(gql_client: PersistentGraphQLClient) -> UUID:
    """Fetch the UUID of the 'org_unit_hierarchy' facet.

    Args:
        gql_client: The GraphQL client to run our queries on.

    Returns:
        The UUID of 'org_unit_hierarchy'.
    """
    # TODO: Optimize with better filters in MO
    # Having user-key filters would help a lot

    # Fetch all facets to find org_unit_hierarchy's UUID
    query = gql(
        """
        query FacetQuery {
            facets {
                uuid
                user_key
            }
        }
        """
    )
    result = await gql_client.execute(query)
    # Construct a user-key to uuid map of all facets
    facet_map = dict(map(itemgetter("user_key", "uuid"), result["facets"]))
    org_unit_hierarchy_uuid = facet_map["org_unit_hierarchy"]
    return UUID(org_unit_hierarchy_uuid)


async def fetch_org_unit_hierarchy_class_uuid(
    gql_client: PersistentGraphQLClient,
    org_unit_hierarchy_uuid: UUID,
    class_user_key: str,
) -> UUID:
    """Fetch the UUID of the given class within the 'org_unit_hierarchy' facet.

    Args:
        gql_client: The GraphQL client to run our queries on.
        class_user_key: User-key of the class to find UUID for.

    Returns:
        The UUID of class.
    """
    # TODO: Optimize with better filters in MO
    # Having user-key filters would help a lot, so would facet filter on classes.

    # Fetch all classes under org_unit_hierarchy to find the class's UUID
    query = gql(
        """
        query ClassQuery($uuids: [UUID!]) {
            facets(uuids: $uuids) {
                classes {
                    uuid
                    user_key
                }
            }
        }
        """
    )
    result = await gql_client.execute(query, {"uuids": [str(org_unit_hierarchy_uuid)]})
    # Construct a user-key to uuid map of all classes
    class_map = dict(
        map(itemgetter("user_key", "uuid"), one(result["facets"])["classes"])
    )
    class_uuid = class_map[class_user_key]
    return UUID(class_uuid)


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


async def fetch_org_unit(
    gql_client: PersistentGraphQLClient, uuid: UUID
) -> OrganisationUnit:
    """Fetch an organisation unit from MO using GraphQL.

    Args:
        gql_client: The GraphQL client to run our queries on.
        uuid: UUID of the organisation unit to fetch.

    Returns:
        The organisation unit object.
    """
    query = gql(
        """
        query OrgUnitQuery($uuids: [UUID!]) {
            org_units(uuids: $uuids) {
                objects {
                    uuid
                    user_key
                    validity {
                        from
                        to
                    }
                    name
                    parent_uuid
                    org_unit_hierarchy_uuid: org_unit_hierarchy
                    org_unit_type_uuid: unit_type_uuid
                    org_unit_level_uuid
                }
            }
        }
        """
    )
    logger.debug("Fetching org-unit via GraphQL", uuid=uuid)
    result = await gql_client.execute(query, {"uuids": [str(uuid)]})
    obj = one(one(result["org_units"])["objects"])
    logger.debug("GraphQL obj", obj=obj)
    org_unit = OrganisationUnit.from_simplified_fields(
        uuid=obj["uuid"],
        user_key=obj["user_key"],
        name=obj["name"],
        parent_uuid=obj["parent_uuid"],
        org_unit_hierarchy_uuid=obj["org_unit_hierarchy_uuid"],
        org_unit_type_uuid=obj["org_unit_type_uuid"],
        org_unit_level_uuid=obj["org_unit_level_uuid"],
        from_date=obj["validity"]["from"],
        to_date=obj["validity"]["to"],
    )
    logger.debug("Organisation Unit", org_unit=org_unit)
    return org_unit


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


async def get_line_management_uuid(
    gql_client: PersistentGraphQLClient,
    line_management_uuid: Optional[UUID],
    line_management_user_key: str,
) -> UUID:
    """Get the UUID of the line_management class.

    Args:
        gql_client: The GraphQL client to run our queries on (if required).
        line_management_uuid: The UUID (if provided) of the class.
        line_management_user_key: The user-key of the class.

    Returns:
        The UUID of class.
    """
    if line_management_uuid:
        return line_management_uuid
    org_unit_hierarchy_uuid = await fetch_org_unit_hierarchy_uuid(gql_client)
    line_management_uuid = await fetch_org_unit_hierarchy_class_uuid(
        gql_client, org_unit_hierarchy_uuid, line_management_user_key
    )
    logger.debug(
        "Line management uuid not set, fetched",
        user_key=line_management_user_key,
        uuid=line_management_uuid,
    )
    return line_management_uuid


async def get_hidden_uuid(
    gql_client: PersistentGraphQLClient,
    hidden_uuid: Optional[UUID],
    hidden_user_key: str,
) -> UUID:
    """Get the UUID of the hidden class.

    Args:
        gql_client: The GraphQL client to run our queries on (if required).
        hidden_uuid: The UUID (if provided) of the class.
        hidden_user_key: The user-key of the class.

    Returns:
        The UUID of class.
    """
    if hidden_uuid:
        return hidden_uuid
    org_unit_hierarchy_uuid = await fetch_org_unit_hierarchy_uuid(gql_client)
    hidden_uuid = await fetch_org_unit_hierarchy_class_uuid(
        gql_client, org_unit_hierarchy_uuid, hidden_user_key
    )
    logger.debug(
        "Hidden uuid not set, fetched",
        user_key=hidden_user_key,
        uuid=hidden_uuid,
    )
    return hidden_uuid


async def update_line_management(
    gql_client: PersistentGraphQLClient,
    model_client: ModelClient,
    settings: Settings,
    uuid: UUID,
) -> bool:
    """Update line management information for the provided organisation unit.

    An organisation unit is part of line management iff:
    * The SD unit-level is NY{x}-niveau or
    * The SD unit-level is Afdelings-niveau and people are attached to it.

    Additionally this function also hides organisation units iff:
    * Their user-key is contained within hidden_user_key or a child of it.

    Args:
        gql_client: The GraphQL client to run queries on.
        model_client: The MO Model client to modify MO with.
        settings: The integration settings module.
        uuid: UUID of the organisation unit to recalculate.

    Returns:
        Whether an update was made.
    """
    # Determine the desired org_unit_hierarchy class uuid
    new_org_unit_hierarchy: UUID | None = None
    if settings.enable_hide_logic and await should_hide(
        gql_client, uuid, settings.hidden
    ):
        logger.debug("Organisation Unit needs to be hidden", uuid=uuid)
        new_org_unit_hierarchy = await get_hidden_uuid(
            gql_client,
            settings.hidden_uuid,
            settings.hidden_user_key,
        )
    elif await is_line_management(gql_client, uuid):
        logger.debug("Organisation Unit needs to be in line management", uuid=uuid)
        new_org_unit_hierarchy = await get_line_management_uuid(
            gql_client,
            settings.line_management_uuid,
            settings.line_management_user_key,
        )

    # Fetch the current object and see if we need to update it
    org_unit = await fetch_org_unit(gql_client, uuid)
    if org_unit.org_unit_hierarchy == new_org_unit_hierarchy:
        logger.debug("Not updating org_unit_hierarchy, already good", uuid=uuid)
        return False

    # Prepare the updated object for writing
    org_unit = org_unit.copy(
        update={
            "org_unit_hierarchy_uuid": new_org_unit_hierarchy,
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
