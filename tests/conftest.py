# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
# pylint: disable=redefined-outer-name
"""This module contains pytest specific code, fixtures and helpers."""
from typing import Any
from typing import Callable
from typing import Generator

import pytest
from _pytest.monkeypatch import MonkeyPatch
from fastapi import FastAPI
from fastapi.testclient import TestClient

import orggatekeeper.main
from orggatekeeper.config import get_settings


@pytest.fixture()
def set_settings(
    monkeypatch: MonkeyPatch,
) -> Generator[Callable[..., None], None, None]:
    """Set settings via kwargs callback."""

    def _inner(**kwargs: Any) -> None:
        for key, value in kwargs.items():
            monkeypatch.setenv(key, value)

    yield _inner


@pytest.fixture(autouse=True)
def setup_client_secret(monkeypatch: MonkeyPatch) -> Generator[None, None, None]:
    """Set the CLIENT_SECRET environmental variable to hunter2 by default."""
    monkeypatch.setenv("CLIENT_SECRET", "hunter2")
    monkeypatch.setenv("FASTRAMQPI__CLIENT_SECRET", "hunter2")
    get_settings.cache_clear()
    yield


@pytest.fixture
def teardown_client_secret(monkeypatch: MonkeyPatch) -> Generator[None, None, None]:
    """Set the CLIENT_SECRET environmental variable to hunter2 by default."""
    monkeypatch.delenv("CLIENT_SECRET")
    monkeypatch.delenv("FASTRAMQPI__CLIENT_SECRET")
    get_settings.cache_clear()
    yield


@pytest.fixture(autouse=True)
def disable_metrics(monkeypatch: MonkeyPatch) -> Generator[None, None, None]:
    """Disable metrics by setting ENABLE_METRICS to false by default."""
    monkeypatch.setenv("FASTRAMQPI__ENABLE_METRICS", "false")
    get_settings.cache_clear()
    yield


@pytest.fixture
def enable_metrics(monkeypatch: MonkeyPatch) -> Generator[None, None, None]:
    """Enable metrics by setting ENABLE_METRICS to true on demand."""
    monkeypatch.setenv("FASTRAMQPI__ENABLE_METRICS", "true")
    get_settings.cache_clear()
    yield


@pytest.fixture
def fastapi_app_builder() -> Generator[Callable[[], FastAPI], None, None]:
    """Fixture for generating FastAPI apps."""
    # pylint: disable=unnecessary-lambda
    yield lambda: orggatekeeper.main.create_app()


@pytest.fixture
def fastapi_app(
    fastapi_app_builder: Callable[[], FastAPI]
) -> Generator[FastAPI, None, None]:
    """Fixture for the FastAPI app."""
    yield fastapi_app_builder()


@pytest.fixture
def test_client_builder(
    fastapi_app_builder: Callable[[], FastAPI]
) -> Generator[Callable[[], TestClient], None, None]:
    """Fixture for generating FastAPI test clients."""
    yield lambda: TestClient(fastapi_app_builder())


@pytest.fixture
def test_client(
    test_client_builder: Callable[[], TestClient]
) -> Generator[TestClient, None, None]:
    """Fixture for the FastAPI test client."""
    yield test_client_builder()
