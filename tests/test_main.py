# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
"""Test the fetch_org_unit function."""

from collections.abc import Callable
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import call
from unittest.mock import patch
from uuid import UUID
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from orggatekeeper.main import build_information
from orggatekeeper.main import create_app
from orggatekeeper.main import update_build_information
from tests import DEFAULT_AMQP_URL
from tests import ORG_UUID


def clear_metric_value(metric: Any) -> None:
    """Get the value of a given metric with the given label-set.

    Args:
        metric: The metric to query.
        labels: The label-set to query with.

    Returns:
        The metric value.
    """
    metric.clear()


def test_build_information() -> None:
    """Test that build metrics are updated as expected."""
    clear_metric_value(build_information)
    assert build_information._value == {}  # pylint: disable=protected-access
    update_build_information("1.0.0", "cafebabe")
    assert build_information._value == {  # pylint: disable=protected-access
        "version": "1.0.0",
        "hash": "cafebabe",
    }


@pytest.fixture
def fastapi_app_builder() -> Generator[Callable[..., FastAPI], None, None]:
    """Fixture for the FastAPI app builder."""

    def builder(*args: Any, default_args: bool = True, **kwargs: Any) -> FastAPI:
        if default_args:
            kwargs.setdefault(
                "fastramqpi",
                {
                    "client_secret": "hunter2",
                    "client_id": "orggatekeeper",
                    "enable_metrics": False,
                    "amqp": {"url": DEFAULT_AMQP_URL},
                },
            )
        return create_app(*args, **kwargs)

    yield builder


@pytest.fixture
def fastapi_app(
    fastapi_app_builder: Callable[..., FastAPI],
) -> Generator[FastAPI, None, None]:
    """Fixture for the FastAPI app."""
    yield fastapi_app_builder()


@pytest.fixture
def test_client_builder(
    fastapi_app_builder: Callable[..., FastAPI],
    mock_amqp_settings: pytest.MonkeyPatch,
) -> Generator[Callable[..., TestClient], None, None]:
    """Fixture for the FastAPI test client builder."""

    def builder(*args: Any, **kwargs: Any) -> TestClient:
        return TestClient(fastapi_app_builder(*args, **kwargs))

    yield builder


@pytest.fixture
def test_client(
    test_client_builder: Callable[..., TestClient],
) -> Generator[TestClient, None, None]:
    """Fixture for the FastAPI test client."""
    yield test_client_builder()


@patch("orggatekeeper.api.update_line_management", return_value=AsyncMock())
async def test_trigger_uuid_endpoint(
    update_line_management_mock: AsyncMock,
    test_client_builder: Callable[..., TestClient],
) -> None:
    """Test the trigger uuid endpoint on our app."""

    test_client = test_client_builder()
    response = test_client.post("/trigger/0a9d7211-16a1-47e1-82da-7ec8480e7487")
    assert response.status_code == 200
    assert response.json() == {"status": "OK"}
    assert update_line_management_mock.mock_calls == [
        call(uuid=UUID("0a9d7211-16a1-47e1-82da-7ec8480e7487"))
    ]


@patch("orggatekeeper.api.update_line_management", return_value=AsyncMock())
@patch("orggatekeeper.main.construct_context")
async def test_ensure_no_unset_endpoint_ok(
    construct_context: MagicMock,
    update_line_management_mock: AsyncMock,
    test_client_builder: Callable[..., TestClient],
) -> None:
    """Test the ensure-no-unset endpoint when no orgunit is unset."""

    construct_context.return_value = {
        "legacy_graphql_session": AsyncMock(),
    }
    with patch("orggatekeeper.api.get_org_units_with_no_hierarchy", return_value=[]):
        test_client = test_client_builder()
        response = test_client.post("/ensure-no-unset")
    assert response.status_code == 200
    assert response.json() == {"status": "OK"}
    update_line_management_mock.assert_not_called()


@patch("orggatekeeper.main.construct_context")
@patch("orggatekeeper.api.update_line_management", return_value=AsyncMock())
async def test_check_unset_endpoint_updates(
    update_line_management_mock: AsyncMock,
    construct_context: MagicMock,
    test_client_builder: Callable[..., TestClient],
) -> None:
    """Test the ensure-no-unset endpoint without org_unit_hierarchy unset"""
    uuids = [uuid4(), uuid4(), uuid4()]
    context = {
        "legacy_model_client": AsyncMock(),
        "legacy_graphql_session": AsyncMock(),
        "user_context": {"settings": MagicMock()},
        "org_uuid": ORG_UUID,
    }
    construct_context.return_value = context

    with patch("orggatekeeper.api.get_org_units_with_no_hierarchy", return_value=uuids):
        test_client = test_client_builder()
        response = test_client.post("/ensure-no-unset")
    assert response.status_code == 200
    assert response.json() == {"status": "Updated 3 orgunits"}
    assert update_line_management_mock.mock_calls == [
        call(**context, uuid=uuid) for uuid in uuids
    ]
