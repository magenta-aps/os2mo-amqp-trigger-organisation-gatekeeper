# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
"""Test the mo.py module"""
from typing import Any
from unittest.mock import MagicMock

from orggatekeeper.mo import fetch_org_uuid
from tests import ORG_UUID


async def test_fetch_org_uuid() -> None:
    # Arrange
    async def execute(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"org": {"uuid": str(ORG_UUID)}}

    mock_gql_client = MagicMock()
    mock_gql_client.execute = execute

    # Act
    uuid = await fetch_org_uuid(mock_gql_client)

    # Assert
    assert ORG_UUID == uuid


# TODO: move the rest of the "fetch" tests from test_calculate.py to this module
# (will be done shortly in a separate MR)
