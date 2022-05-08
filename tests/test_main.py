# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
# pylint: disable=redefined-outer-name
"""Test the fetch_org_unit function."""
from datetime import datetime
from functools import partial
from typing import Any
from typing import cast
from typing import Set
from typing import Tuple
from unittest.mock import AsyncMock
from unittest.mock import call
from unittest.mock import MagicMock
from unittest.mock import patch
from uuid import uuid4

from ramqp.mo_models import ObjectType
from ramqp.mo_models import PayloadType
from ramqp.mo_models import RequestType
from ramqp.mo_models import ServiceType

from orggatekeeper.config import get_settings as original_get_settings
from orggatekeeper.main import callback_generator
from orggatekeeper.main import main
from orggatekeeper.main import update_counter


def get_metric_value(metric: Any, labels: Tuple[str]) -> float:
    """Get the value of a given metric with the given label-set.

    Args:
        metric: The metric to query.
        labels: The label-set to query with.

    Returns:
        The metric value.
    """
    # pylint: disable=protected-access
    metric = metric.labels(*labels)._value
    return cast(float, metric.get())


def clear_metric_value(metric: Any) -> None:
    """Get the value of a given metric with the given label-set.

    Args:
        metric: The metric to query.
        labels: The label-set to query with.

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
    # pylint: disable=protected-access
    return set(metric._metrics.keys())


@patch("orggatekeeper.main.update_line_management")
async def test_update_metric(update_line_management: MagicMock) -> None:
    """Test that our update_counter metric is updated as expected."""
    payload = PayloadType(uuid=uuid4(), object_uuid=uuid4(), time=datetime.now())

    callback_caller = partial(
        callback_generator(MagicMock(), MagicMock(), MagicMock()), MagicMock()
    )

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


@patch("orggatekeeper.main.MOAMQPSystem")
@patch("orggatekeeper.main.callback_generator")
@patch("orggatekeeper.main.start_http_server")
@patch("orggatekeeper.main.get_settings")
@patch("orggatekeeper.main.run_forever")
def test_main(
    run_forever: MagicMock,
    get_settings: MagicMock,
    start_http_server: MagicMock,
    callback_generator: MagicMock,
    MOAMQPSystem: MagicMock,  # pylint: disable=invalid-name
) -> None:
    """Test that main behaves as we expect."""
    run_forever.return_value = None

    settings = original_get_settings(client_secret="hunter2")
    get_settings.return_value = settings

    amqp_system = AsyncMock()
    amqp_system.register = MagicMock()
    MOAMQPSystem.return_value = amqp_system

    callback = MagicMock()
    callback_generator.return_value = callback

    main()

    get_settings.assert_called_once()
    start_http_server.assert_called_once_with(8011)
    MOAMQPSystem.assert_called_once()

    assert len(amqp_system.mock_calls) == 8

    assert amqp_system.mock_calls[0] == call.register(
        ServiceType.ORG_UNIT, ObjectType.ASSOCIATION, RequestType.WILDCARD
    )
    assert amqp_system.mock_calls[1] == call.register()(callback)

    assert amqp_system.mock_calls[2] == call.register(
        ServiceType.ORG_UNIT, ObjectType.ENGAGEMENT, RequestType.WILDCARD
    )
    assert amqp_system.mock_calls[3] == call.register()(callback)

    assert amqp_system.mock_calls[4] == call.register(
        ServiceType.ORG_UNIT, ObjectType.ORG_UNIT, RequestType.WILDCARD
    )
    assert amqp_system.mock_calls[5] == call.register()(callback)

    assert amqp_system.mock_calls[6] == call.start(
        queue_prefix="os2mo-amqp-trigger-organisation-gatekeeper"
    )
    assert amqp_system.mock_calls[7] == call.stop()
