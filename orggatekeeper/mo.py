# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
"""Module for fetching information (e.g. facet and class UUIDs) from MO"""
from typing import Optional
from uuid import UUID

import structlog
from gql import gql
from more_itertools import one
from raclients.graph.client import PersistentGraphQLClient
from ramodels.mo import OrganisationUnit

logger = structlog.get_logger()


async def fetch_class_uuid(
    gql_client: PersistentGraphQLClient,
    class_user_key: str,
) -> UUID:
    """Fetch the UUID of the given class.

    Args:
        gql_client: The GraphQL client to run our queries on.
        class_user_key: User-key of the class to find UUID for.

    Returns:
        The UUID of class.
    """

    query = gql("""
        query ClassQuery($user_keys: [String!]) {
            classes(user_keys: $user_keys) {
                uuid
            }
        }
        """)
    result = await gql_client.execute(query, {"user_keys": [class_user_key]})
    class_uuid = one(result["classes"])["uuid"]
    return UUID(class_uuid)


async def fetch_org_uuid(gql_client: PersistentGraphQLClient) -> UUID:
    """
    Fetch the UUID of the LoRa organisation.

    Args:
        gql_client: The GraphQL client to run our queries on.

    Returns:
        The UUID of the LoRa organisation.
    """
    query = gql("""
        query OrganisationUuidQuery {
            org {
                uuid
            }
        }
        """)
    result = await gql_client.execute(query)
    return UUID(result["org"]["uuid"])


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
    query = gql("""
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
        """)
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


async def get_class_uuid(
    gql_client: PersistentGraphQLClient,
    class_uuid: Optional[UUID],
    class_user_key: str,
) -> UUID:
    """Get the UUID of the org_unit_hierarchy class.

    Args:
        gql_client: The GraphQL client to run our queries on (if required).
        class_uuid: The UUID (if provided) of the class.
        class_user_key: The user-key of the class.

    Returns:
        The UUID of class.
    """
    if class_uuid:
        return class_uuid
    class_uuid = await fetch_class_uuid(gql_client, class_user_key)
    logger.debug(
        "org_unit_hierarchy class uuid not set, fetched",
        user_key=class_user_key,
        uuid=class_uuid,
    )
    return class_uuid


async def get_it_system_uuid(
    gql_client: PersistentGraphQLClient, user_key: str
) -> UUID:
    """Find the uuid of an it-system from its user_key

    Args:
        gql_client: The GraphQL client to run our queries on.
        user_key: user_key of the it-system to look up.

    Returns:
        UUID of the it-system
    """
    query = gql("""
        query ITSystemQuery($user_keys: [String!]) {
          itsystems(user_keys: $user_keys) {
            uuid
          }
        }
        """)

    result = await gql_client.execute(query, {"user_keys": [user_key]})
    it_system = one(result["itsystems"])
    logger.debug(
        f"Looked up it_system with user_key={user_key}, found",
        it_system=it_system,
    )
    return UUID(it_system["uuid"])
