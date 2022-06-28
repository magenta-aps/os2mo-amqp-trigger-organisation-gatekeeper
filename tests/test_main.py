# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=protected-access
# pylint: disable=unused-argument
"""Test the fetch_org_unit function."""
import asyncio
import random
from datetime import datetime
from functools import partial
from time import monotonic
from typing import Any
from typing import Callable
from typing import cast
from typing import Set
from typing import Tuple
from unittest.mock import AsyncMock
from unittest.mock import call
from unittest.mock import MagicMock
from unittest.mock import patch
from uuid import UUID
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from more_itertools import one
from ramqp.mo.models import PayloadType

from fastramqpi.config import Settings
from fastramqpi.main import build_information
from fastramqpi.main import construct_clients
from fastramqpi.main import update_build_information
from orggatekeeper.main import amqp_router
from orggatekeeper.main import create_fastramqpi
from orggatekeeper.main import gather_with_concurrency
from orggatekeeper.main import organisation_gatekeeper_callback
from orggatekeeper.main import update_counter


def get_metric_value(metric: Any, labels: Tuple[str]) -> float:
    """Get the value of a given metric with the given label-set.

    Args:
        metric: The metric to query.
        labels: The label-set to query with.

    Returns:
        The metric value.
    """
    metric = metric.labels(*labels)._value
    return cast(float, metric.get())


def clear_metric_value(metric: Any) -> None:
    """Get the value of a given metric with the given label-set.

    Args:
        metric: The metric to query.

    Returns:
        The metric value.
    """
    metric.clear()


def get_metric_labels(metric: Any) -> Set[Tuple[str]]:
    """Get the label-set for a given metric.

    Args:
        metric: The metric to query.

    Returns:
        The label-set.
    """
    return set(metric._metrics.keys())


@patch("orggatekeeper.main.update_line_management")
async def test_update_metric(update_line_management: MagicMock) -> None:
    """Test that our update_counter metric is updated as expected."""
    payload = PayloadType(uuid=uuid4(), object_uuid=uuid4(), time=datetime.now())
    context = {
        "graphql_session": MagicMock(),
        "model_client": MagicMock(),
        "user_context": {"settings": MagicMock()},
    }
    callback_caller = partial(organisation_gatekeeper_callback, context)

    clear_metric_value(update_counter)
    assert get_metric_labels(update_counter) == set()

    # Returning false, counts up false once
    update_line_management.return_value = False
    await callback_caller(payload)
    assert get_metric_labels(update_counter) == {("False",)}
    assert get_metric_value(update_counter, ("False",)) == 1.0

    # Returning false, counts up false once
    update_line_management.return_value = False
    await callback_caller(payload)
    assert get_metric_labels(update_counter) == {("False",)}
    assert get_metric_value(update_counter, ("False",)) == 2.0

    # Returning true, counts up true once
    update_line_management.return_value = True
    await callback_caller(payload)
    assert get_metric_labels(update_counter) == {("False",), ("True",)}
    assert get_metric_value(update_counter, ("False",)) == 2.0
    assert get_metric_value(update_counter, ("True",)) == 1.0

    # Returning true, counts up true once
    update_line_management.return_value = True
    await callback_caller(payload)
    assert get_metric_labels(update_counter) == {("False",), ("True",)}
    assert get_metric_value(update_counter, ("False",)) == 2.0
    assert get_metric_value(update_counter, ("True",)) == 2.0


def test_build_information() -> None:
    """Test that build metrics are updated as expected."""
    clear_metric_value(build_information)
    assert build_information._value == {}
    update_build_information("1.0.0", "cafebabe")
    assert build_information._value == {
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
        ]
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
        ]
    )
    end = monotonic()
    duration = end - start
    assert duration > 0.3


async def test_root_endpoint(test_client: TestClient) -> None:
    """Test the root endpoint on our app."""
    response = test_client.get("/")
    assert response.status_code == 200
    assert response.json() == {"name": "orggatekeeper"}


async def test_metrics_endpoint(
    enable_metrics: None, test_client_builder: Callable[[], TestClient]
) -> None:
    """Test the metrics endpoint on our app."""
    test_client = test_client_builder()
    response = test_client.get("/metrics")
    assert response.status_code == 200
    assert "# TYPE orggatekeeper_changes_created gauge" in response.text
    assert "# TYPE build_information_info gauge" in response.text


@patch("orggatekeeper.main.create_app")
@patch("orggatekeeper.main.update_line_management", new_callable=AsyncMock)
async def test_trigger_all_endpoint(
    update_line_management: AsyncMock,
    create_app: MagicMock,
    test_client_builder: Callable[..., TestClient],
) -> None:
    """Test the trigger all endpoint on our app."""
    uuids = [uuid4() for _ in range(random.randint(1, 10))]

    gql_session = AsyncMock()
    gql_session.execute.return_value = {
        "org_units": [{"uuid": str(uuid)} for uuid in uuids]
    }
    fastramqpi = create_fastramqpi()
    create_app.return_value = fastramqpi.get_app()
    fastramqpi._context["graphql_session"] = gql_session
    model_client = MagicMock()
    fastramqpi._context["model_client"] = model_client
    settings = MagicMock()
    fastramqpi._context["user_context"]["settings"] = settings

    test_client = test_client_builder()
    response = test_client.post("/trigger/all")
    assert response.status_code == 200
    assert response.json() == {"status": "OK"}
    assert len(gql_session.execute.mock_calls) == 1
    assert update_line_management.mock_calls == [
        call(
            gql_session=gql_session,
            model_client=model_client,
            settings=settings,
            uuid=uuid,
        )
        for uuid in uuids
    ]


@patch("orggatekeeper.main.create_app")
@patch("orggatekeeper.main.update_line_management", new_callable=AsyncMock)
async def test_trigger_uuid_endpoint(
    update_line_management: AsyncMock,
    create_app: MagicMock,
    test_client_builder: Callable[..., TestClient],
) -> None:
    """Test the trigger uuid endpoint on our app."""

    fastramqpi = create_fastramqpi()
    create_app.return_value = fastramqpi.get_app()
    gql_session = MagicMock()
    fastramqpi._context["graphql_session"] = gql_session
    model_client = MagicMock()
    fastramqpi._context["model_client"] = model_client
    settings = MagicMock()
    fastramqpi._context["user_context"]["settings"] = settings

    test_client = test_client_builder()
    response = test_client.post("/trigger/0a9d7211-16a1-47e1-82da-7ec8480e7487")
    assert response.status_code == 200
    assert response.json() == {"status": "OK"}
    assert update_line_management.mock_calls == [
        call(
            gql_session=gql_session,
            model_client=model_client,
            settings=settings,
            uuid=UUID("0a9d7211-16a1-47e1-82da-7ec8480e7487"),
        )
    ]


async def test_register() -> None:
    """Test that our router registered the right events."""
    # Assert that only one function is registered on the router
    route_function = one(amqp_router.registry)
    routing_keys = amqp_router.registry[route_function]
    assert routing_keys == {
        "org_unit.engagement.*",
        "org_unit.org_unit.*",
        "org_unit.association.*",
    }


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
@patch("orggatekeeper.main.create_app")
async def test_readiness_endpoint(
    create_app: MagicMock,
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
    model_client.get.return_value = model_client_response

    amqp_system = MagicMock()
    amqp_system.healthcheck.return_value = amqp_ok

    fastramqpi = create_fastramqpi()
    create_app.return_value = fastramqpi.get_app()
    fastramqpi._context["user_context"]["gql_client"] = gql_client
    fastramqpi._context["user_context"]["model_client"] = model_client
    fastramqpi._context["amqpsystem"] = amqp_system

    test_client = test_client_builder()

    response = test_client.get("/health/ready")
    assert response.status_code == expected

    assert len(gql_client.execute.mock_calls) == 1
    assert model_client.mock_calls == [call.get("/service/o/"), call.get().json()]
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
@patch("orggatekeeper.main.create_app")
async def test_readiness_endpoint_exception(
    create_app: MagicMock,
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
    model_client.get.return_value = model_client_response

    amqp_system = MagicMock()
    if amqp_ok:
        amqp_system.healthcheck.return_value = True
    else:
        amqp_system.healthcheck.side_effect = ValueError("BOOM")

    fastramqpi = create_fastramqpi()
    create_app.return_value = fastramqpi.get_app()
    fastramqpi._context["user_context"]["gql_client"] = gql_client
    fastramqpi._context["user_context"]["model_client"] = model_client
    fastramqpi._context["amqpsystem"] = amqp_system

    test_client = test_client_builder()

    response = test_client.get("/health/ready")
    assert response.status_code == expected


@patch("fastramqpi.main.GraphQLClient")
def test_gql_client_created_with_timeout(mock_gql_client: MagicMock) -> None:
    """Test that GraphQLClient is called with timeout setting"""

    # Arrange
    settings = Settings(graphql_timeout=15)

    # Act
    construct_clients(settings)

    # Assert
    assert 15 == mock_gql_client.call_args.kwargs["httpx_client_kwargs"]["timeout"]
    assert 15 == mock_gql_client.call_args.kwargs["execute_timeout"]
