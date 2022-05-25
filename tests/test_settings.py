# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
"""Test our settings handling."""
import pytest
from pydantic import SecretStr
from pydantic import ValidationError

from orggatekeeper.config import get_settings


def test_missing_client_secret() -> None:
    """Test that we must add client_secret to construct settings."""

    get_settings.cache_clear()
    with pytest.raises(ValidationError) as excinfo:
        get_settings()
    assert "client_secret\n  field required" in str(excinfo.value)


def test_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that we can construct settings."""
    get_settings.cache_clear()

    settings = get_settings(client_secret="hunter2")
    assert isinstance(settings.client_secret, SecretStr)
    assert settings.client_secret.get_secret_value() == "hunter2"

    monkeypatch.setenv("CLIENT_SECRET", "AzureDiamond")
    settings = get_settings()
    assert isinstance(settings.client_secret, SecretStr)
    assert settings.client_secret.get_secret_value() == "AzureDiamond"


def test_bad_port() -> None:
    """Test that bad port numbers are rejected."""
    get_settings.cache_clear()

    with pytest.raises(ValidationError) as excinfo:
        get_settings(client_secret="hunter2", metrics_port=-1)
    assert "metrics_port\n  ensure this value is greater than or equal to 0" in str(
        excinfo.value
    )

    with pytest.raises(ValidationError) as excinfo:
        get_settings(client_secret="hunter2", metrics_port=70000)
    assert "metrics_port\n  ensure this value is less than or equal to 65535" in str(
        excinfo.value
    )
