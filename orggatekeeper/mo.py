# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
"""Module for fetching information (e.g. facet and class UUIDs) from MO"""
from operator import itemgetter
from typing import Optional
from uuid import UUID

import structlog
from gql import gql
from more_itertools import one
from raclients.graph.client import PersistentGraphQLClient
from ramodels.mo import OrganisationUnit

logger = structlog.get_logger()


async def fetch_org_unit_hierarchy_facet_uuid(
    gql_client: PersistentGraphQLClient,
) -> UUID:
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


async def fetch_org_uuid(gql_client: PersistentGraphQLClient) -> UUID:
    """
    Fetch the UUID of the LoRa organisation.

    Args:
        gql_client: The GraphQL client to run our queries on.

    Returns:
        The UUID of the LoRa organisation.
    """
    query = gql(
        """
        query OrganisationUuidQuery {
            org {
                uuid
            }
        }
        """
    )
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
    org_unit_hierarchy_uuid = await fetch_org_unit_hierarchy_facet_uuid(gql_client)
    class_uuid = await fetch_org_unit_hierarchy_class_uuid(
        gql_client, org_unit_hierarchy_uuid, class_user_key
    )
    logger.debug(
        "org_unit_hierarchy class uuid not set, fetched",
        user_key=class_user_key,
        uuid=class_uuid,
    )
    return class_uuid
