# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
"""Test the mo.py module"""
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID
from uuid import uuid4

from graphql import DocumentNode
from more_itertools import one
from ramodels.mo import OrganisationUnit

from orggatekeeper.calculate import fetch_org_unit
from orggatekeeper.mo import fetch_org_unit_hierarchy_class_uuid
from orggatekeeper.mo import fetch_org_unit_hierarchy_facet_uuid
from orggatekeeper.mo import fetch_org_uuid
from tests import ORG_UUID


async def test_fetch_org_unit() -> None:
    """Test that fetch_org_unit can build an OrganisationUnit."""
    uuid: UUID = UUID("08eaf849-e9f9-53e0-b6b9-3cd45763ecbb")
    params: dict[str, Any] = {}

    async def execute(*args: Any, **kwargs: Any) -> dict[str, Any]:
        params["args"] = args
        params["kwargs"] = kwargs

        return {
            "org_units": [
                {
                    "objects": [
                        {
                            "uuid": str(uuid),
                            "user_key": "Viuf skole",
                            "validity": {
                                "from": "1960-01-01T00:00:00+01:00",
                                "to": None,
                            },
                            "name": "Viuf skole",
                            "parent_uuid": "2665d8e0-435b-5bb6-a550-f275692984ef",
                            "org_unit_hierarchy_uuid": None,
                            "org_unit_type_uuid": (
                                "9d2ac723-d5e5-4e7f-9c7f-b207bd223bc2"
                            ),
                            "org_unit_level_uuid": (
                                "d4c6fb4a-233f-4b85-a77a-6dcdb13ee0db"
                            ),
                        }
                    ]
                }
            ]
        }

    session = MagicMock()
    session.execute = execute
    result = await fetch_org_unit(session, uuid)
    assert len(params["args"]) == 2
    assert isinstance(params["args"][0], DocumentNode)
    assert params["args"][1] == {"uuids": [str(uuid)]}

    assert isinstance(result, OrganisationUnit)
    assert result.uuid == uuid


async def test_fetch_org_unit_hierarchy_facet_uuid() -> None:
    """Test that fetch_org_unit_hierarchy can find our facet uuid."""
    params: dict[str, Any] = {}
    org_unit_hierarchy_uuid: UUID = UUID("fc3c8bde-51fc-4975-876a-c14165416d12")

    async def execute(*args: Any, **kwargs: Any) -> dict[str, Any]:
        params["args"] = args
        params["kwargs"] = kwargs

        return {
            "facets": [
                {"uuid": "7384589a-4bc0-467d-a3dd-92c9b51854ec", "user_key": "morass"},
                {
                    "uuid": str(org_unit_hierarchy_uuid),
                    "user_key": "org_unit_hierarchy",
                },
                {
                    "uuid": "ff3be635-d1b2-4995-bb9f-3cab9fbc5dee",
                    "user_key": "mismatch",
                },
            ]
        }

    session = MagicMock()
    session.execute = execute
    result = await fetch_org_unit_hierarchy_facet_uuid(session)
    assert isinstance(one(params["args"]), DocumentNode)

    assert isinstance(result, UUID)
    assert result == org_unit_hierarchy_uuid


# TODO: Test Cache of cached async methods


async def test_fetch_org_unit_hierarchy_class_uuid() -> None:
    """Test that fetch_org_unit_hierarchy_class can find our class uuid."""
    params: dict[str, Any] = {}

    classes = {
        "key1": "24029af8-8289-4f37-9a03-efb4a06e7a29",
        "key2": "e75f5433-da24-479d-a2c8-fa19e98846f0",
        "key3": "b40876ea-7453-4c4c-944b-b349719d08b1",
    }

    async def execute(*args: Any, **kwargs: Any) -> dict[str, Any]:
        params["args"] = args
        params["kwargs"] = kwargs

        return {
            "facets": [
                {
                    "classes": [
                        {
                            "uuid": value,
                            "user_key": key,
                        }
                        for key, value in classes.items()
                    ]
                }
            ]
        }

    for key, uuid in classes.items():
        session = MagicMock()
        session.execute = execute
        facet_uuid = uuid4()
        result = await fetch_org_unit_hierarchy_class_uuid(session, facet_uuid, key)
        assert len(params["args"]) == 2
        assert isinstance(params["args"][0], DocumentNode)
        assert params["args"][1] == {"uuids": [str(facet_uuid)]}

        assert isinstance(result, UUID)
        assert result == UUID(uuid)


async def test_fetch_org_uuid() -> None:
    """Test the fetch_org_uuid coroutine"""
    # Arrange
    async def execute(
        *args: Any, **kwargs: Any  # pylint: disable=unused-argument
    ) -> dict[str, Any]:
        return {"org": {"uuid": str(ORG_UUID)}}

    mock_gql_client = MagicMock()
    mock_gql_client.execute = execute

    # Act
    uuid = await fetch_org_uuid(mock_gql_client)

    # Assert
    assert ORG_UUID == uuid


# TODO: move the rest of the "fetch" tests from test_calculate.py to this module
# (will be done shortly in a separate MR)
