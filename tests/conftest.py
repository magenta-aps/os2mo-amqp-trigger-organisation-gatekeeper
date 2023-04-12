# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
# pylint: disable=redefined-outer-name
"""This module contains pytest specific code, fixtures and helpers."""
from datetime import datetime
from typing import Any
from typing import Generator
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch
from uuid import UUID
from uuid import uuid4

import pytest
from ramodels.mo import OrganisationUnit

from orggatekeeper.config import ConnectionSettings
from orggatekeeper.config import Settings
from tests import ORG_UUID


@pytest.fixture
def mock_client_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch environment variable for client secret"""
    monkeypatch.setenv("CLIENT_SECRET", "AzureDiamond")


@pytest.fixture
def mock_amqp_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch environment variable for amqp url."""
    monkeypatch.setenv("AMQP__URL", "amqp://guest:guest@msg_broker:5672/os2mo")


@pytest.fixture
def mock_connection_settings() -> Generator:
    """Patch environment variable for amqp url."""
    yield ConnectionSettings(url="amqp://guest:guest@msg_broker:5672/os2mo")


@pytest.fixture()
def org_unit() -> Generator[OrganisationUnit, None, None]:
    """Construct a dummy OrganisationUnit.

    Return:
        Dummy OrganisationUnit.
    """
    yield OrganisationUnit.from_simplified_fields(
        user_key="AAAA",
        name="Test",
        org_unit_type_uuid=uuid4(),
        org_unit_level_uuid=uuid4(),
        parent_uuid=uuid4(),
        from_date=datetime.now().isoformat(),
    )


@pytest.fixture()
def gql_client() -> Generator[MagicMock, None, None]:
    """Fixture to mock GraphQLClient."""
    yield MagicMock()


@pytest.fixture()
def model_client() -> Generator[AsyncMock, None, None]:
    """Fixture to mock ModelClient."""
    yield AsyncMock()


@pytest.fixture()
def settings() -> Generator:
    """Fixture to mock get_settings."""

    def setup_mock_settings(*args: Any, **kwargs: Any) -> Settings:
        sett = Settings(
            amqp=ConnectionSettings(url="amqp://guest:guest@msg_broker:5672/os2mo"),
            client_secret="hunter2",
            *args,
            **kwargs
        )
        return sett

    yield setup_mock_settings()


@pytest.fixture()
def class_uuid() -> Generator[UUID, None, None]:
    """Fixture to mock get_class_uuid."""
    with patch("orggatekeeper.calculate.get_class_uuid") as get_class_uuid:
        uuid = uuid4()
        get_class_uuid.return_value = uuid
        yield uuid


@pytest.fixture()
def context(
    gql_client: MagicMock, model_client: AsyncMock, settings: Settings
) -> dict[str, Any]:
    """Fixture to generate context"""
    return {
        "gql_client": gql_client,
        "model_client": model_client,
        "settings": settings,
        "org_uuid": ORG_UUID,
    }
