# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
"""Test the mo.py module"""
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

from orggatekeeper.mo import fetch_org_uuid
from orggatekeeper.mo import get_it_system_uuid
from tests import ORG_UUID


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


async def test_get_it_system() -> None:
    """Test the get_it_system_uuid coroutine"""
    it_system_uuid = uuid4()
    # Arrange

    async def execute(
        *args: Any, **kwargs: Any  # pylint: disable=unused-argument
    ) -> dict[str, Any]:
        return {"itsystems": [{"uuid": str(it_system_uuid)}]}

    mock_gql_client = MagicMock()
    mock_gql_client.execute = execute

    # Act
    uuid = await get_it_system_uuid(mock_gql_client, "Any")

    # Assert
    assert it_system_uuid == uuid


# TODO: move the rest of the "fetch" tests from test_calculate.py to this module
# (will be done shortly in a separate MR)
