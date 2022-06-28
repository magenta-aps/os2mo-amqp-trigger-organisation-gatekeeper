# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
# pylint: disable=unused-argument
"""Test our settings handling."""
import pytest
from pydantic import SecretStr
from pydantic import ValidationError

from fastramqpi.config import Settings


def test_missing_client_secret(teardown_client_secret: None) -> None:
    """Test that we must add client_secret to construct settings."""
    with pytest.raises(ValidationError) as excinfo:
        Settings()
    assert "client_secret\n  field required" in str(excinfo.value)


def test_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that we can construct settings."""
    settings = Settings()
    assert isinstance(settings.client_secret, SecretStr)
    assert settings.client_secret.get_secret_value() == "hunter2"

    monkeypatch.setenv("CLIENT_SECRET", "AzureDiamond")
    settings = Settings()
    assert isinstance(settings.client_secret, SecretStr)
    assert settings.client_secret.get_secret_value() == "AzureDiamond"


def test_graphql_timeout_default() -> None:
    """Test that default GraphQL client timeout is set correctly"""
    settings = Settings()
    assert 120 == settings.graphql_timeout


def test_graphql_timeout_non_default() -> None:
    """Test that GraphQL client timeout is set to overridden value"""
    settings = Settings(graphql_timeout=10)
    assert 10 == settings.graphql_timeout
