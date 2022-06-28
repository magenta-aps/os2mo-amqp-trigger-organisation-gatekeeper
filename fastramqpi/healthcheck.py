# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
"""Healthchecking functions."""
import structlog
from gql import gql
from more_itertools import one

from .context import Context


logger = structlog.get_logger()


async def healthcheck_gql(context: Context) -> bool:
    """Check that our GraphQL connection is healthy.

    Args:
        context: Execution context that contains GraphQL client.

    Returns:
        Whether the client is healthy or not.
    """
    gql_client = context["user_context"]["gql_client"]

    query = gql(
        """
        query HealthcheckQuery {
            org {
                uuid
            }
        }
        """
    )
    try:
        result = await gql_client.execute(query)
        if result["org"]["uuid"]:
            return True
    except Exception:  # pylint: disable=broad-except
        logger.exception("Exception occured during GraphQL healthcheck")
    return False


async def healthcheck_model_client(context: Context) -> bool:
    """Check that our ModelClient connection is healthy.

    Args:
        context: Execution context that contains MO model client.

    Returns:
        Whether the client is healthy or not.
    """
    model_client = context["user_context"]["model_client"]

    try:
        response = await model_client.get("/service/o/")
        result = response.json()
        if one(result)["uuid"]:
            return True
    except Exception:  # pylint: disable=broad-except
        logger.exception("Exception occured during GraphQL healthcheck")
    return False
