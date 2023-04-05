# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
# pylint: disable=unused-argument
"""Test our settings handling."""
import pytest
from pydantic import SecretStr
from pydantic import ValidationError

from orggatekeeper.config import get_settings


def test_missing_client_secret(mock_amqp_settings: pytest.MonkeyPatch) -> None:
    """Test that we must add client_secret to construct settings."""

    get_settings.cache_clear()
    with pytest.raises(ValidationError) as excinfo:
        get_settings()
    assert "client_secret\n  field required" in str(excinfo.value)


def test_happy_path(
    mock_amqp_settings: pytest.MonkeyPatch, mock_client_secret: pytest.MonkeyPatch
) -> None:
    """Test that we can construct settings."""
    get_settings.cache_clear()

    settings = get_settings(client_secret="hunter2")
    assert isinstance(settings.client_secret, SecretStr)
    assert settings.client_secret.get_secret_value() == "hunter2"

    settings = get_settings()
    assert isinstance(settings.client_secret, SecretStr)
    assert settings.client_secret.get_secret_value() == "AzureDiamond"


def test_graphql_timeout_default(mock_amqp_settings: pytest.MonkeyPatch) -> None:
    """Test that default GraphQL client timeout is set correctly"""
    get_settings.cache_clear()
    settings = get_settings(client_secret="not important")
    assert 120 == settings.graphql_timeout


def test_graphql_timeout_non_default(mock_amqp_settings: pytest.MonkeyPatch) -> None:
    """Test that GraphQL client timeout is set to overridden value"""
    get_settings.cache_clear()
    settings = get_settings(client_secret="not important", graphql_timeout=10)
    assert 10 == settings.graphql_timeout
