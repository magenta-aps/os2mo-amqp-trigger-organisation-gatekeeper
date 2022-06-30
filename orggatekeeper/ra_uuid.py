# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
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


async def fetch_org_unit_hierarchy_facet_uuid(gql_client: PersistentGraphQLClient) -> UUID:
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
