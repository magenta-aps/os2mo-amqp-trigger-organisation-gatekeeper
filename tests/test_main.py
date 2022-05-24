# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
"""Test the fetch_org_unit function."""
from datetime import datetime
from typing import Any
from typing import cast
from typing import Set
from typing import Tuple
from unittest.mock import call
from unittest.mock import MagicMock
from unittest.mock import patch
from uuid import uuid4

from ramqp.mo_models import ObjectType
from ramqp.mo_models import PayloadType
from ramqp.mo_models import RequestType
from ramqp.mo_models import ServiceType

from orggatekeeper.config import get_settings as original_get_settings
from orggatekeeper.main import main
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

    clear_metric_value(update_counter)
    assert get_metric_labels(update_counter) == set()

    # Returning false, counts up false once
    update_line_management.return_value = False
    await organisation_gatekeeper_callback(None, None, None, payload)
    assert get_metric_labels(update_counter) == {("False",)}
    assert get_metric_value(update_counter, ("False",)) == 1.0

    # Returning false, counts up false once
    update_line_management.return_value = False
    await organisation_gatekeeper_callback(None, None, None, payload)
    assert get_metric_labels(update_counter) == {("False",)}
    assert get_metric_value(update_counter, ("False",)) == 2.0

    # Returning true, counts up true once
    update_line_management.return_value = True
    await organisation_gatekeeper_callback(None, None, None, payload)
    assert get_metric_labels(update_counter) == {("False",), ("True",)}
    assert get_metric_value(update_counter, ("False",)) == 2.0
    assert get_metric_value(update_counter, ("True",)) == 1.0

    # Returning true, counts up true once
    update_line_management.return_value = True
    await organisation_gatekeeper_callback(None, None, None, payload)
    assert get_metric_labels(update_counter) == {("False",), ("True",)}
    assert get_metric_value(update_counter, ("False",)) == 2.0
    assert get_metric_value(update_counter, ("True",)) == 2.0


@patch("orggatekeeper.main.MOAMQPSystem")
@patch("orggatekeeper.main.start_http_server")
@patch("orggatekeeper.main.get_settings")
def test_main(
    get_settings: MagicMock,
    start_http_server: MagicMock,
    MOAMQPSystem: MagicMock,  # pylint: disable=invalid-name
) -> None:
    """Test that main behaves as we expect."""
    get_settings.return_value = original_get_settings(client_secret="hunter2")

    amqp_system = MagicMock()
    MOAMQPSystem.return_value = amqp_system

    main()

    get_settings.assert_called_once()
    start_http_server.assert_called_once_with(8011)
    MOAMQPSystem.assert_called_once_with()
    assert amqp_system.mock_calls == [
        call.register(ServiceType.ORG_UNIT, ObjectType.ORG_UNIT, RequestType.WILDCARD),
        call.register()(organisation_gatekeeper_callback),
        call.run_forever(queue_prefix="os2mo-amqp-trigger-organisation-gatekeeper"),
    ]
