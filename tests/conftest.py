# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
"""This module contains pytest specific code, fixtures and helpers."""
import pytest


@pytest.fixture
def mock_client_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch environment variable for client secret"""
    monkeypatch.setenv("CLIENT_SECRET", "AzureDiamond")


@pytest.fixture
def mock_amqp_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch environment variable for amqp url."""
    monkeypatch.setenv("AMQP__URL", "amqp://guest:guest@msg_broker:5672/os2mo")
