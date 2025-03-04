# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
# pylint: disable=redefined-outer-name
"""This module contains pytest specific code, fixtures and helpers."""

from collections.abc import Callable
from collections.abc import Generator
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch
from uuid import UUID
from uuid import uuid4

import pytest
from ramodels.mo import OrganisationUnit

from orggatekeeper.config import Settings
from tests import DEFAULT_AMQP_URL
from tests import ORG_UUID


@pytest.fixture
def mock_amqp_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch environment variable for amqp url."""
    monkeypatch.setenv("AMQP__URL", DEFAULT_AMQP_URL)


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
def set_settings() -> Generator[Callable[..., Settings], None, None]:
    """Fixture to mock get_settings."""

    def setup_mock_settings(
        *args: Any,
        amqp_url: str = DEFAULT_AMQP_URL,
        client_secret: str = "hunter2",
        client_id: str = "orggatekeeper_test",
        **kwargs: Any,
    ) -> Settings:
        settings = Settings(
            *args,
            amqp={"url": amqp_url},
            client_secret=client_secret,
            client_id=client_id,
            **kwargs,
        )
        return settings

    yield setup_mock_settings


@pytest.fixture()
def mock_settings(
    set_settings: Callable[..., Settings],
) -> Generator[Settings, None, None]:
    """Fixture to mock get_settings."""
    yield set_settings()


@pytest.fixture()
def class_uuid() -> Generator[UUID, None, None]:
    """Fixture to mock get_class_uuid."""
    with patch("orggatekeeper.calculate.get_class_uuid") as get_class_uuid:
        uuid = uuid4()
        get_class_uuid.return_value = uuid
        yield uuid


@pytest.fixture()
def context(
    gql_client: MagicMock, model_client: AsyncMock, mock_settings: Settings
) -> dict[str, Any]:
    """Fixture to generate context"""
    return {
        "gql_client": gql_client,
        "model_client": model_client,
        "settings": mock_settings,
        "org_uuid": ORG_UUID,
    }
