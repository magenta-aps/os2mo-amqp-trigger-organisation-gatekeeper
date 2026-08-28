# SPDX-FileCopyrightText: Magenta ApS <https://magenta.dk>
# SPDX-License-Identifier: MPL-2.0

from datetime import datetime
from typing import Any
from unittest.mock import MagicMock
from unittest.mock import patch
from uuid import uuid4

from fastramqpi.ramqp.mo import PayloadType

from orggatekeeper.events import association_callback
from orggatekeeper.events import engagement_callback
from orggatekeeper.events import ituser_callback
from orggatekeeper.events import org_unit_handler


@patch("orggatekeeper.calculate.update_line_management")
async def test_callback_engagement(
    update_line_management_mock: MagicMock, context: dict[str, Any]
) -> None:
    """Test that changes to engagements results in calls to update_line_management
    with the org_unit_uuid of an engagement.
    """
    org_unit_uuid = uuid4()
    payload = PayloadType(uuid=uuid4(), object_uuid=uuid4(), time=datetime.now())
    with patch(
        "orggatekeeper.events.get_orgunit_from_engagement",
        return_value={org_unit_uuid},
    ):
        await engagement_callback(context, payload=payload, _=None)
    update_line_management_mock.assert_called_once_with(**context, uuid=org_unit_uuid)


@patch("orggatekeeper.calculate.update_line_management")
async def test_callback_engagement_missing_uuid(
    update_line_management_mock: MagicMock, context: dict[str, Any]
) -> None:
    """Test that changes to engagements results in calls to update_line_management
    with the org_unit_uuid of an engagement.
    """
    payload = PayloadType(uuid=uuid4(), object_uuid=uuid4(), time=datetime.now())
    with patch(
        "orggatekeeper.events.get_orgunit_from_engagement",
        side_effect=ValueError,
    ):
        await engagement_callback(context, payload=payload, _=None)
    update_line_management_mock.assert_not_called()


@patch("orggatekeeper.calculate.update_line_management")
async def test_callback_association(
    update_line_management_mock: MagicMock, context: dict[str, Any]
) -> None:
    """Test that changes to associations results in calls to update_line_management
    with the org_unit_uuid of an association.
    """
    payload = PayloadType(uuid=uuid4(), object_uuid=uuid4(), time=datetime.now())
    with patch(
        "orggatekeeper.events.get_orgunit_from_association", return_value={uuid4()}
    ):
        await association_callback(context, payload=payload, _=None)
    update_line_management_mock.assert_called_once()


@patch("orggatekeeper.calculate.update_line_management")
async def test_callback_association_missing_uuid(
    update_line_management_mock: MagicMock, context: dict[str, Any]
) -> None:
    """Test that changes to associations results in calls to update_line_management
    with the org_unit_uuid of an association.
    """
    payload = PayloadType(uuid=uuid4(), object_uuid=uuid4(), time=datetime.now())
    with patch(
        "orggatekeeper.events.get_orgunit_from_association", side_effect=ValueError
    ):
        await association_callback(context, payload=payload, _=None)
    update_line_management_mock.assert_not_called()


@patch("orggatekeeper.calculate.update_line_management")
async def test_callback_ituser(
    update_line_management_mock: MagicMock, context: dict[str, Any]
) -> None:
    """Test that changes to itusers results in calls to update_line_management
    with the org_unit_uuid of an ituser.
    """
    payload = PayloadType(uuid=uuid4(), object_uuid=uuid4(), time=datetime.now())
    with patch("orggatekeeper.events.get_orgunit_from_ituser", return_value={uuid4()}):
        await ituser_callback(context, payload=payload, _=None)
    update_line_management_mock.assert_called_once()


@patch("orggatekeeper.calculate.update_line_management")
async def test_callback_ituser_missing_uuid(
    update_line_management_mock: MagicMock, context: dict[str, Any]
) -> None:
    """Test that changes to associations results in calls to update_line_management
    with the org_unit_uuid of an association.
    """
    payload = PayloadType(uuid=uuid4(), object_uuid=uuid4(), time=datetime.now())
    with patch("orggatekeeper.events.get_orgunit_from_ituser", side_effect=ValueError):
        await ituser_callback(context, payload=payload, _=None)
    update_line_management_mock.assert_not_called()


@patch("orggatekeeper.calculate.update_line_management")
async def test_callback_org_unit(
    update_line_management_mock: MagicMock,
    context: dict[str, Any],
) -> None:
    """Test that changes calls update line management with an org_units uuid"""
    uuid = uuid4()
    await org_unit_handler(context, uuid=uuid, _=None)
    update_line_management_mock.assert_called_once_with(**context, uuid=uuid)
