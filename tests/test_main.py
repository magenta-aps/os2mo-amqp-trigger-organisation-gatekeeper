# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
"""Test the fetch_org_unit function."""

import asyncio
from collections.abc import Callable
from collections.abc import Generator
from time import monotonic
from typing import Any
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import call
from unittest.mock import patch
from uuid import UUID
from uuid import uuid4

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from fastapi.testclient import TestClient

from orggatekeeper.config import Settings
from orggatekeeper.main import build_information
from orggatekeeper.main import construct_clients
from orggatekeeper.main import create_app
from orggatekeeper.main import gather_with_concurrency
from orggatekeeper.main import update_build_information
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


async def test_gather_with_concurrency() -> None:
    """Test gather with concurrency."""
    start = monotonic()
    await asyncio.gather(
        *[
            asyncio.sleep(0.1),
            asyncio.sleep(0.1),
            asyncio.sleep(0.1),
        ]
    )
    end = monotonic()
    duration = end - start
    assert duration < 0.15

    start = monotonic()
    await gather_with_concurrency(
        3,
        *[
            asyncio.sleep(0.1),
            asyncio.sleep(0.1),
            asyncio.sleep(0.1),
        ],
    )
    end = monotonic()
    duration = end - start
    assert duration < 0.15

    start = monotonic()
    await gather_with_concurrency(
        1,
        *[
            asyncio.sleep(0.1),
            asyncio.sleep(0.1),
            asyncio.sleep(0.1),
        ],
    )
    end = monotonic()
    duration = end - start
    assert duration > 0.3


@pytest.fixture
def fastapi_app_builder() -> Generator[Callable[..., FastAPI], None, None]:
    """Fixture for the FastAPI app builder."""

    def builder(*args: Any, default_args: bool = True, **kwargs: Any) -> FastAPI:
        if default_args:
            kwargs["client_secret"] = "hunter2"
            kwargs["expose_metrics"] = False
        return create_app(*args, **kwargs)

    yield builder


@pytest.fixture
def fastapi_app(
    fastapi_app_builder: Callable[..., FastAPI],
) -> Generator[FastAPI, None, None]:
    """Fixture for the FastAPI app."""
    yield fastapi_app_builder(client_secret="hunter2", expose_metrics=False)


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


async def test_root_endpoint(test_client: TestClient) -> None:
    """Test the root endpoint on our app."""
    response = test_client.get("/")
    assert response.status_code == 200
    assert response.json() == {"name": "orggatekeeper"}


async def test_metrics_endpoint(test_client_builder: Callable[..., TestClient]) -> None:
    """Test the metrics endpoint on our app."""
    test_client = test_client_builder(default_args=False, client_secret="hunter2")
    response = test_client.get("/metrics")
    assert response.status_code == 200
    assert "# TYPE build_information_info gauge" in response.text


@patch("fastapi.BackgroundTasks.add_task", return_value=AsyncMock())
@patch("orggatekeeper.main.construct_context")
async def test_trigger_all_endpoint(
    construct_context: MagicMock,
    backgroundtask_mock: AsyncMock,
    test_client_builder: Callable[..., TestClient],
) -> None:
    """Test the trigger all endpoint on our app."""
    gql_client = AsyncMock()
    gql_client.execute.return_value = {
        "org_units": {
            "objects": [
                {"uuid": str(uuid4())},
                {"uuid": str(uuid4())},
                {"uuid": str(uuid4())},
            ]
        }
    }
    construct_context.return_value = {
        "model_client": AsyncMock(),
        "gql_client": gql_client,
        "settings": MagicMock(),
        "org_uuid": ORG_UUID,
    }
    test_client = test_client_builder()
    response = test_client.post("/trigger/all")
    assert response.status_code == 202
    assert response.json() == {"status": "Background job triggered"}
    assert len(gql_client.execute.mock_calls) == 1
    assert len(backgroundtask_mock.call_args[0]) == 5


@patch("orggatekeeper.main.update_line_management", return_value=AsyncMock())
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


@patch("orggatekeeper.main.fetch_org_uuid")
@patch("orggatekeeper.main.MOAMQPSystem")
@patch("orggatekeeper.calculate.MORouter")
async def test_lifespan(
    mo_router: MagicMock,
    mo_amqpsystem: MagicMock,
    mock_fetch_org_uuid: MagicMock,
    fastapi_app: FastAPI,
) -> None:
    """Test that our lifespan events are handled as expected."""
    amqp_system = MagicMock()
    amqp_system.start = AsyncMock()
    amqp_system.stop = AsyncMock()

    mo_amqpsystem.return_value = amqp_system
    mock_fetch_org_uuid.return_value = ORG_UUID

    router = MagicMock()
    mo_router.return_value = router

    assert not amqp_system.mock_calls

    # Fire startup event on entry, and shutdown on exit
    async with LifespanManager(fastapi_app):
        assert len(router.mock_calls) == 0

        # Clean mock to only capture shutdown changes
        amqp_system.reset_mock()


async def test_liveness_endpoint(test_client: TestClient) -> None:
    """Test the liveness endpoint on our app."""
    response = test_client.get("/health/live")
    assert response.status_code == 204


@pytest.mark.parametrize(
    "amqp_ok,gql_ok,model_ok,expected",
    [
        (True, True, True, 204),
        (False, True, True, 503),
        (True, False, True, 503),
        (True, True, False, 503),
        (True, False, False, 503),
        (False, True, False, 503),
        (False, False, True, 503),
        (False, False, False, 503),
    ],
)
@patch("orggatekeeper.main.construct_context")
async def test_readiness_endpoint(
    construct_context: MagicMock,
    test_client_builder: Callable[..., TestClient],
    amqp_ok: bool,
    gql_ok: bool,
    model_ok: bool,
    expected: int,
) -> None:
    """Test the readiness endpoint handles errors."""
    gql_client = AsyncMock()
    if gql_ok:
        gql_client.execute.return_value = {
            "org": {"uuid": "35304fa6-ff84-4ea4-aac9-a285995ab45b"}
        }
    else:
        gql_client.execute.return_value = {
            "errors": [{"message": "Something went wrong"}]
        }

    model_client_response = MagicMock()
    if model_ok:
        model_client_response.json.return_value = [
            {"uuid": "35304fa6-ff84-4ea4-aac9-a285995ab45b"}
        ]
    else:
        model_client_response.json.return_value = "BOOM"
    model_client = AsyncMock()
    model_client.async_httpx_client.get.return_value = model_client_response

    amqp_system = MagicMock()
    amqp_system.healthcheck.return_value = amqp_ok

    construct_context.return_value = {
        "gql_client": gql_client,
        "model_client": model_client,
        "amqp_system": amqp_system,
    }
    test_client = test_client_builder()

    response = test_client.get("/health/ready")
    assert response.status_code == expected

    assert len(gql_client.execute.mock_calls) == 1
    print(model_client.mock_calls)
    assert model_client.mock_calls == [
        call.async_httpx_client.get("/service/o/"),
        call.async_httpx_client.get().json(),
    ]
    assert amqp_system.mock_calls == [call.healthcheck()]


@pytest.mark.parametrize(
    "amqp_ok,gql_ok,model_ok,expected",
    [
        (True, True, True, 204),
        (False, True, True, 503),
        (True, False, True, 503),
        (True, True, False, 503),
        (True, False, False, 503),
        (False, True, False, 503),
        (False, False, True, 503),
        (False, False, False, 503),
    ],
)
@patch("orggatekeeper.main.construct_context")
async def test_readiness_endpoint_exception(
    construct_context: MagicMock,
    test_client_builder: Callable[..., TestClient],
    amqp_ok: bool,
    gql_ok: bool,
    model_ok: bool,
    expected: int,
) -> None:
    """Test the readiness endpoint handled exceptions nicely."""
    gql_client = AsyncMock()
    if gql_ok:
        gql_client.execute.return_value = {
            "org": {"uuid": "35304fa6-ff84-4ea4-aac9-a285995ab45b"}
        }
    else:
        gql_client.execute.side_effect = ValueError("BOOM")

    model_client_response = MagicMock()
    if model_ok:
        model_client_response.json.return_value = [
            {"uuid": "35304fa6-ff84-4ea4-aac9-a285995ab45b"}
        ]
    else:
        model_client_response.json.side_effect = ValueError("BOOM")
    model_client = AsyncMock()
    model_client.async_httpx_client.get.return_value = model_client_response

    amqp_system = MagicMock()
    if amqp_ok:
        amqp_system.healthcheck.return_value = True
    else:
        amqp_system.healthcheck.side_effect = ValueError("BOOM")

    construct_context.return_value = {
        "gql_client": gql_client,
        "model_client": model_client,
        "amqp_system": amqp_system,
    }
    test_client = test_client_builder()

    response = test_client.get("/health/ready")
    assert response.status_code == expected


@patch("orggatekeeper.main.PersistentGraphQLClient")
def test_gql_client_created_with_timeout(
    gql_client: MagicMock,
    set_settings: Callable[..., Settings],
) -> None:
    """Test that PersistentGraphQLClient is called with timeout setting"""

    # Arrange
    settings = set_settings(graphql_timeout=15)

    # Act
    construct_clients(settings)

    # Assert
    assert gql_client.call_args.kwargs["httpx_client_kwargs"]["timeout"] == 15
    assert gql_client.call_args.kwargs["execute_timeout"] == 15


@patch("orggatekeeper.calculate.update_line_management", return_value=AsyncMock())
@patch("orggatekeeper.main.construct_context")
async def test_ensure_no_unset_endpoint_ok(
    construct_context: MagicMock,
    update_line_management_mock: AsyncMock,
    test_client_builder: Callable[..., TestClient],
) -> None:
    """Test the ensure-no-unset endpoint when no orgunit is unset."""

    construct_context.return_value = {
        "gql_client": AsyncMock(),
    }
    with patch("orggatekeeper.main.get_org_units_with_no_hierarchy", return_value=[]):
        test_client = test_client_builder()
        response = test_client.post("/ensure-no-unset")
    assert response.status_code == 200
    assert response.json() == {"status": "OK"}
    update_line_management_mock.assert_not_called()


@patch("orggatekeeper.main.construct_context")
@patch("orggatekeeper.main.update_line_management", return_value=AsyncMock())
async def test_check_unset_endpoint_updates(
    update_line_management_mock: AsyncMock,
    construct_context: MagicMock,
    test_client_builder: Callable[..., TestClient],
) -> None:
    """Test the ensure-no-unset endpoint without org_unit_hierarchy unset"""
    uuids = [uuid4(), uuid4(), uuid4()]
    context = {
        "model_client": AsyncMock(),
        "gql_client": AsyncMock(),
        "settings": MagicMock(),
        "org_uuid": ORG_UUID,
    }
    construct_context.return_value = context

    with patch(
        "orggatekeeper.main.get_org_units_with_no_hierarchy", return_value=uuids
    ):
        test_client = test_client_builder()
        response = test_client.post("/ensure-no-unset")
    assert response.status_code == 200
    assert response.json() == {"status": "Updated 3 orgunits"}
    assert update_line_management_mock.mock_calls == [
        call(**context, uuid=uuid) for uuid in uuids
    ]
