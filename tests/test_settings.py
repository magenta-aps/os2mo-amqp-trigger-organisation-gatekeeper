# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
# pylint: disable=unused-argument
"""Test our settings handling."""
import pytest
from pydantic import SecretStr
from pydantic import ValidationError

from orggatekeeper.config import get_settings
from orggatekeeper.config import Settings


def test_missing_client_secret(mock_amqp_settings: pytest.MonkeyPatch) -> None:
    """Test that we must add client_secret to construct settings."""

    get_settings.cache_clear()
    with pytest.raises(ValidationError) as excinfo:
        get_settings()
    assert "client_secret\n  field required" in str(excinfo.value)


def test_happy_path(
    mock_amqp_settings: pytest.MonkeyPatch, mock_client_secret: pytest.MonkeyPatch
) -> None:
    """Test that we can construct and edit settings."""
    get_settings.cache_clear()

    settings = get_settings(client_secret="AzureDiamond")
    assert isinstance(settings.client_secret, SecretStr)
    assert settings.client_secret.get_secret_value() == "AzureDiamond"

    settings = get_settings()
    settings.client_secret = SecretStr("hunter2")
    assert isinstance(settings.client_secret, SecretStr)
    assert settings.client_secret.get_secret_value() == "hunter2"


def test_graphql_timeout_default(settings: Settings) -> None:
    """Test that default GraphQL client timeout is set correctly"""

    assert 120 == settings.graphql_timeout
