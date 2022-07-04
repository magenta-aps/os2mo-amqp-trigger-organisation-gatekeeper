# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
"""Test the fetch_org_unit function."""
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=too-many-arguments
from datetime import datetime
from functools import partial
from typing import Any
from typing import Awaitable
from typing import Callable
from typing import Generator
from unittest.mock import AsyncMock
from unittest.mock import call
from unittest.mock import MagicMock
from unittest.mock import patch
from uuid import UUID
from uuid import uuid4

import pytest
from graphql import DocumentNode
from more_itertools import one
from ramodels.mo import OrganisationUnit
from ramodels.mo import Validity
from ramodels.mo._shared import OrgUnitHierarchy

from orggatekeeper.calculate import fetch_org_unit
from orggatekeeper.calculate import get_hidden_uuid
from orggatekeeper.calculate import get_line_management_uuid
from orggatekeeper.calculate import is_line_management
from orggatekeeper.calculate import should_hide
from orggatekeeper.calculate import update_line_management
from orggatekeeper.config import get_settings
from orggatekeeper.config import Settings
from orggatekeeper.mo import fetch_org_unit_hierarchy_class_uuid
from orggatekeeper.mo import fetch_org_unit_hierarchy_facet_uuid

from tests import ORG_UUID


async def test_fetch_org_unit() -> None:
    """Test that fetch_org_unit can build an OrganisationUnit."""
    uuid: UUID = UUID("08eaf849-e9f9-53e0-b6b9-3cd45763ecbb")
    params: dict[str, Any] = {}

    async def execute(*args: Any, **kwargs: Any) -> dict[str, Any]:
        params["args"] = args
        params["kwargs"] = kwargs

        return {
            "org_units": [
                {
                    "objects": [
                        {
                            "uuid": str(uuid),
                            "user_key": "Viuf skole",
                            "validity": {
                                "from": "1960-01-01T00:00:00+01:00",
                                "to": None,
                            },
                            "name": "Viuf skole",
                            "parent_uuid": "2665d8e0-435b-5bb6-a550-f275692984ef",
                            "org_unit_hierarchy_uuid": None,
                            "org_unit_type_uuid": (
                                "9d2ac723-d5e5-4e7f-9c7f-b207bd223bc2"
                            ),
                            "org_unit_level_uuid": (
                                "d4c6fb4a-233f-4b85-a77a-6dcdb13ee0db"
                            ),
                        }
                    ]
                }
            ]
        }

    session = MagicMock()
    session.execute = execute
    result = await fetch_org_unit(session, uuid)
    assert len(params["args"]) == 2
    assert isinstance(params["args"][0], DocumentNode)
    assert params["args"][1] == {"uuids": [str(uuid)]}

    assert isinstance(result, OrganisationUnit)
    assert result.uuid == uuid


async def test_fetch_org_unit_hierarchy_facet_uuid() -> None:
    """Test that fetch_org_unit_hierarchy can find our facet uuid."""
    params: dict[str, Any] = {}
    org_unit_hierarchy_uuid: UUID = UUID("fc3c8bde-51fc-4975-876a-c14165416d12")

    async def execute(*args: Any, **kwargs: Any) -> dict[str, Any]:
        params["args"] = args
        params["kwargs"] = kwargs

        return {
            "facets": [
                {"uuid": "7384589a-4bc0-467d-a3dd-92c9b51854ec", "user_key": "morass"},
                {
                    "uuid": str(org_unit_hierarchy_uuid),
                    "user_key": "org_unit_hierarchy",
                },
                {
                    "uuid": "ff3be635-d1b2-4995-bb9f-3cab9fbc5dee",
                    "user_key": "mismatch",
                },
            ]
        }

    session = MagicMock()
    session.execute = execute
    result = await fetch_org_unit_hierarchy_facet_uuid(session)
    assert isinstance(one(params["args"]), DocumentNode)

    assert isinstance(result, UUID)
    assert result == org_unit_hierarchy_uuid


# TODO: Test Cache of cached async methods


async def test_fetch_org_unit_hierarchy_class_uuid() -> None:
    """Test that fetch_org_unit_hierarchy_class can find our class uuid."""
    params: dict[str, Any] = {}

    classes = {
        "key1": "24029af8-8289-4f37-9a03-efb4a06e7a29",
        "key2": "e75f5433-da24-479d-a2c8-fa19e98846f0",
        "key3": "b40876ea-7453-4c4c-944b-b349719d08b1",
    }

    async def execute(*args: Any, **kwargs: Any) -> dict[str, Any]:
        params["args"] = args
        params["kwargs"] = kwargs

        return {
            "facets": [
                {
                    "classes": [
                        {
                            "uuid": value,
                            "user_key": key,
                        }
                        for key, value in classes.items()
                    ]
                }
            ]
        }

    for key, uuid in classes.items():
        session = MagicMock()
        session.execute = execute
        facet_uuid = uuid4()
        result = await fetch_org_unit_hierarchy_class_uuid(session, facet_uuid, key)
        assert len(params["args"]) == 2
        assert isinstance(params["args"][0], DocumentNode)
        assert params["args"][1] == {"uuids": [str(facet_uuid)]}

        assert isinstance(result, UUID)
        assert result == UUID(uuid)


@pytest.mark.parametrize(
    "org_unit_level_user_key,num_engagements,num_assocations,expected",
    [
        # Engagements and associations do not matter with NY
        ("NY0-niveau", 0, 0, True),
        ("NY0-niveau", 42, 0, True),
        ("NY0-niveau", 0, 42, True),
        ("NY0-niveau", 42, 42, True),
        # Single digit is good
        ("NY1-niveau", 0, 0, True),
        ("NY6-niveau", 0, 0, True),
        ("NY9-niveau", 0, 0, True),
        # Double digit and negative are not
        ("NY10-niveau", 0, 0, False),
        ("NY-1-niveau", 0, 0, False),
        # If afdelings-niveau we need either engagements or assocations
        ("Afdelings-niveau", 0, 0, False),
        ("Afdelings-niveau", 42, 0, True),
        ("Afdelings-niveau", 0, 42, True),
        ("Afdelings-niveau", 42, 42, True),
    ],
)
async def test_is_line_management(
    org_unit_level_user_key: str,
    num_engagements: int,
    num_assocations: int,
    expected: bool,
) -> None:
    """Test that is_line_management works as expected."""
    params: dict[str, Any] = {}

    async def execute(*args: Any, **kwargs: Any) -> dict[str, Any]:
        params["args"] = args
        params["kwargs"] = kwargs

        return {
            "org_units": [
                {
                    "objects": [
                        {
                            "org_unit_level": {"user_key": org_unit_level_user_key},
                            "engagements": [
                                {"uuid": uuid4()} for _ in range(num_engagements)
                            ],
                            "associations": [
                                {"uuid": uuid4()} for _ in range(num_assocations)
                            ],
                        }
                    ]
                }
            ]
        }

    uuid = uuid4()
    session = MagicMock()
    session.execute = execute
    result = await is_line_management(session, uuid)
    assert len(params["args"]) == 2
    assert isinstance(params["args"][0], DocumentNode)
    assert params["args"][1] == {"uuids": [str(uuid)]}
    assert result == expected


async def test_should_hide_no_list() -> None:
    """Test that calculate_hidden returns false when given empty list."""
    uuid = uuid4()
    session = MagicMock()
    result = await should_hide(session, uuid, [])
    assert result is False


@pytest.mark.parametrize(
    "uuid,hidden_list,expected",
    [
        # Directly on top-level
        (UUID("0020f400-2777-4ef9-bfcb-5cdbb561d583"), ["QQQQ"], False),
        (UUID("0020f400-2777-4ef9-bfcb-5cdbb561d583"), ["AAAA"], True),
        (UUID("0020f400-2777-4ef9-bfcb-5cdbb561d583"), ["AAAB"], False),
        # Immediate child
        (UUID("8b54ca22-66cb-4f46-94ae-ee0a0c370bcf"), ["QQQQ"], False),
        (UUID("8b54ca22-66cb-4f46-94ae-ee0a0c370bcf"), ["AAAA"], True),
        (UUID("8b54ca22-66cb-4f46-94ae-ee0a0c370bcf"), ["AAAB"], True),
        (UUID("8b54ca22-66cb-4f46-94ae-ee0a0c370bcf"), ["AABA"], False),
        (UUID("8b54ca22-66cb-4f46-94ae-ee0a0c370bcf"), ["AAAC"], False),
        # Nested child
        (UUID("f29d62b6-4aab-44e5-95e4-be602dceaf8b"), ["QQQQ"], False),
        (UUID("f29d62b6-4aab-44e5-95e4-be602dceaf8b"), ["AAAA"], True),
        (UUID("f29d62b6-4aab-44e5-95e4-be602dceaf8b"), ["AAAB"], True),
        (UUID("f29d62b6-4aab-44e5-95e4-be602dceaf8b"), ["AABA"], False),
        (UUID("f29d62b6-4aab-44e5-95e4-be602dceaf8b"), ["AAAC"], True),
    ],
)
async def test_should_hide_parent(
    uuid: UUID, hidden_list: list[str], expected: bool
) -> None:
    """Test that should_hide works as expected."""
    parent_map = {
        UUID("0020f400-2777-4ef9-bfcb-5cdbb561d583"): {
            "user_key": "AAAA",
            "parent_uuid": None,
        },
        UUID("8b54ca22-66cb-4f46-94ae-ee0a0c370bcf"): {
            "user_key": "AAAB",
            "parent_uuid": UUID("0020f400-2777-4ef9-bfcb-5cdbb561d583"),
        },
        UUID("f29d62b6-4aab-44e5-95e4-be602dceaf8b"): {
            "user_key": "AAAC",
            "parent_uuid": UUID("8b54ca22-66cb-4f46-94ae-ee0a0c370bcf"),
        },
        UUID("58fd9427-cde0-4740-b696-31690f21f831"): {
            "user_key": "AABA",
            "parent_uuid": UUID("0020f400-2777-4ef9-bfcb-5cdbb561d583"),
        },
    }

    params: dict[str, Any] = {}

    async def execute(*args: Any, **kwargs: Any) -> dict[str, Any]:
        params["args"] = args
        params["kwargs"] = kwargs

        uuid = UUID(one(args[1]["uuids"]))

        return {"org_units": [{"objects": [parent_map[uuid]]}]}

    session = MagicMock()
    session.execute = execute
    result = await should_hide(session, uuid, hidden_list)
    assert len(params["args"]) == 2
    assert isinstance(params["args"][0], DocumentNode)
    assert isinstance(params["args"][1], dict)
    UUID(params["args"][1]["uuids"][0])
    assert result == expected


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
        from_date=datetime.now(),
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

    def setup_mock_settings(*args: Any, **kwargs: Any) -> Settings:
        settings = get_settings(client_secret="hunter2", *args, **kwargs)
        return settings

    yield setup_mock_settings


@pytest.fixture()
def settings(set_settings: Callable[..., Settings]) -> Generator[Settings, None, None]:
    """Fixture to mock get_settings."""
    yield set_settings()


@pytest.fixture()
def line_management_uuid(
    gql_client: MagicMock, settings: Settings
) -> Generator[UUID, None, None]:
    """Fixture to mock get_line_management_uuid."""
    with patch(
        "orggatekeeper.calculate.get_line_management_uuid"
    ) as get_line_management_uuid:
        line_management_uuid = uuid4()
        get_line_management_uuid.return_value = line_management_uuid
        yield line_management_uuid


@pytest.fixture()
def hidden_uuid(
    gql_client: MagicMock, settings: Settings
) -> Generator[UUID, None, None]:
    """Fixture to mock get_hidden_uuid."""
    with patch("orggatekeeper.calculate.get_hidden_uuid") as get_hidden_uuid:
        hidden_uuid = uuid4()
        get_hidden_uuid.return_value = hidden_uuid
        yield hidden_uuid


@pytest.fixture()
def seeded_update_line_management(
    gql_client: MagicMock, model_client: AsyncMock, settings: Settings
) -> Generator[Callable[[UUID], Awaitable[bool]], None, None]:
    """Fixture to generate update_line_management function."""
    seeded_update_line_management = partial(
        update_line_management, gql_client, model_client, settings, ORG_UUID
    )
    yield seeded_update_line_management


@patch("orggatekeeper.calculate.is_line_management")
@patch("orggatekeeper.calculate.should_hide")
@patch("orggatekeeper.calculate.fetch_org_unit")
async def test_update_line_management_no_change(
    fetch_org_unit: MagicMock,
    should_hide: MagicMock,
    is_line_management: MagicMock,
    gql_client: MagicMock,
    model_client: AsyncMock,
    seeded_update_line_management: Callable[[UUID], Awaitable[bool]],
    org_unit: OrganisationUnit,
) -> None:
    """Test that update_line_management can do noop."""
    should_hide.return_value = False
    is_line_management.return_value = False
    fetch_org_unit.return_value = org_unit

    uuid = org_unit.uuid
    result = await seeded_update_line_management(uuid)
    assert result is False

    should_hide.assert_called_once_with(gql_client, uuid, [])
    is_line_management.assert_called_once_with(gql_client, uuid)
    fetch_org_unit.assert_called_once_with(gql_client, uuid)
    model_client.assert_not_called()


@patch("orggatekeeper.calculate.should_hide")
@patch("orggatekeeper.calculate.fetch_org_unit")
async def test_update_line_management_dry_run(
    fetch_org_unit: MagicMock,
    should_hide: MagicMock,
    gql_client: MagicMock,
    model_client: AsyncMock,
    set_settings: Callable[..., Settings],
    hidden_uuid: MagicMock,
    org_unit: OrganisationUnit,
) -> None:
    """Test that update_line_management can set hidden_uuid."""
    settings = set_settings(dry_run=True)
    seeded_update_line_management = partial(
        update_line_management, gql_client, model_client, settings, ORG_UUID
    )

    should_hide.return_value = True
    fetch_org_unit.return_value = org_unit

    uuid = org_unit.uuid
    result = await seeded_update_line_management(uuid)
    assert result is True

    should_hide.assert_called_once_with(gql_client, uuid, [])
    fetch_org_unit.assert_called_once_with(gql_client, uuid)
    model_client.edit.assert_not_called()


@patch("orggatekeeper.calculate.datetime")
@patch("orggatekeeper.calculate.should_hide")
@patch("orggatekeeper.calculate.fetch_org_unit")
async def test_update_line_management_hidden(
    fetch_org_unit: MagicMock,
    should_hide: MagicMock,
    mock_datetime: MagicMock,
    gql_client: MagicMock,
    model_client: AsyncMock,
    settings: Settings,
    hidden_uuid: UUID,
    seeded_update_line_management: Callable[[UUID], Awaitable[bool]],
    org_unit: OrganisationUnit,
) -> None:
    """Test that update_line_management can set hidden_uuid."""
    should_hide.return_value = True
    fetch_org_unit.return_value = org_unit

    now = datetime.now()
    mock_datetime.datetime.now.return_value = now

    uuid = org_unit.uuid
    result = await seeded_update_line_management(uuid)
    assert result is True

    should_hide.assert_called_once_with(gql_client, uuid, [])
    fetch_org_unit.assert_called_once_with(gql_client, uuid)
    assert model_client.mock_calls == [
        call.edit(
            [
                org_unit.copy(
                    update={
                        "org_unit_hierarchy": OrgUnitHierarchy(uuid=hidden_uuid),
                        "validity": Validity(from_date=now.date()),
                    }
                )
            ]
        )
    ]


@patch("orggatekeeper.calculate.datetime")
@patch("orggatekeeper.calculate.is_line_management")
@patch("orggatekeeper.calculate.should_hide")
@patch("orggatekeeper.calculate.fetch_org_unit")
async def test_update_line_management_line(
    fetch_org_unit: MagicMock,
    should_hide: MagicMock,
    is_line_management: MagicMock,
    mock_datetime: MagicMock,
    gql_client: MagicMock,
    model_client: AsyncMock,
    settings: Settings,
    line_management_uuid: UUID,
    seeded_update_line_management: Callable[[UUID], Awaitable[bool]],
    org_unit: OrganisationUnit,
) -> None:
    """Test that update_line_management can set line_management_uuid."""
    should_hide.return_value = False
    is_line_management.return_value = True
    fetch_org_unit.return_value = org_unit

    now = datetime.now()
    mock_datetime.datetime.now.return_value = now

    uuid = org_unit.uuid
    result = await seeded_update_line_management(uuid)
    assert result is True

    should_hide.assert_called_once_with(gql_client, uuid, [])
    is_line_management.assert_called_once_with(gql_client, uuid)
    fetch_org_unit.assert_called_once_with(gql_client, uuid)
    assert model_client.mock_calls == [
        call.edit(
            [
                org_unit.copy(
                    update={
                        "org_unit_hierarchy": OrgUnitHierarchy(
                            uuid=line_management_uuid
                        ),
                        "validity": Validity(from_date=now.date()),
                    }
                )
            ]
        )
    ]


@patch("orggatekeeper.calculate.datetime")
@patch("orggatekeeper.calculate.is_line_management")
@patch("orggatekeeper.calculate.should_hide")
@patch("orggatekeeper.calculate.fetch_org_unit")
async def test_update_line_management_line_for_root_org_unit(
    fetch_org_unit: MagicMock,
    should_hide: MagicMock,
    is_line_management: MagicMock,
    mock_datetime: MagicMock,
    gql_client: MagicMock,
    model_client: AsyncMock,
    settings: Settings,
    line_management_uuid: UUID,
    seeded_update_line_management: Callable[[UUID], Awaitable[bool]],
) -> None:
    """
    Test that update_line_management can set line_management_uuid for
    for an root org unit.
    """
    should_hide.return_value = False
    is_line_management.return_value = True
    org_unit = OrganisationUnit.from_simplified_fields(
        user_key="AAAA",
        name="Test",
        org_unit_type_uuid=uuid4(),
        org_unit_level_uuid=uuid4(),
        parent_uuid=ORG_UUID,  # I.e. a root unit
        from_date=datetime.now(),
    )
    fetch_org_unit.return_value = org_unit

    now = datetime.now()
    mock_datetime.datetime.now.return_value = now

    uuid = org_unit.uuid
    result = await seeded_update_line_management(uuid)
    assert result is True

    should_hide.assert_called_once_with(gql_client, uuid, [])
    is_line_management.assert_called_once_with(gql_client, uuid)
    fetch_org_unit.assert_called_once_with(gql_client, uuid)
    assert model_client.mock_calls == [
        call.edit(
            [
                org_unit.copy(
                    update={
                        "org_unit_hierarchy": OrgUnitHierarchy(
                            uuid=line_management_uuid
                        ),
                        "parent": None,  # Since the unit is a root org unit
                        "validity": Validity(from_date=now.date()),
                    }
                )
            ]
        )
    ]


async def test_get_line_management_uuid_preseed() -> None:
    """Test get_line_management_uuid with pre-seeded uuid."""
    uuid = uuid4()
    session = MagicMock()
    settings = get_settings(
        client_secret="hunter2",
        line_management_uuid=uuid,
    )
    line_management_uuid = await get_line_management_uuid(
        session,
        line_management_uuid=settings.line_management_uuid,
        line_management_user_key=settings.line_management_user_key,
    )
    assert line_management_uuid == uuid


@patch("orggatekeeper.mo.fetch_org_unit_hierarchy_facet_uuid", new_callable=AsyncMock)
@patch(
    "orggatekeeper.mo.fetch_org_unit_hierarchy_class_uuid",
    new_callable=AsyncMock,
)
async def test_get_line_management_uuid(
    fetch_org_unit_hierarchy_class_uuid: MagicMock,
    fetch_org_unit_hierarchy_facet_uuid: MagicMock,
) -> None:
    """Test get_line_management_uuid with pre-seeded uuid."""
    facet_uuid = uuid4()
    uuid = uuid4()
    fetch_org_unit_hierarchy_facet_uuid.return_value = facet_uuid
    fetch_org_unit_hierarchy_class_uuid.return_value = uuid

    settings = get_settings(client_secret="hunter2")
    session = MagicMock()
    line_management_uuid = await get_line_management_uuid(
        session,
        line_management_uuid=settings.line_management_uuid,
        line_management_user_key=settings.line_management_user_key,
    )
    assert line_management_uuid == uuid

    fetch_org_unit_hierarchy_class_uuid.assert_called_once_with(
        session, facet_uuid, "linjeorg"
    )
    fetch_org_unit_hierarchy_facet_uuid.assert_called_once_with(session)


async def test_get_hidden_uuid_preseed() -> None:
    """Test get_hidden_uuid with pre-seeded uuid."""
    uuid = uuid4()
    settings = get_settings(
        client_secret="hunter2",
        hidden_uuid=uuid,
    )
    session = MagicMock()
    hidden_uuid = await get_hidden_uuid(
        session,
        hidden_uuid=settings.hidden_uuid,
        hidden_user_key=settings.hidden_user_key,
    )
    assert hidden_uuid == uuid


@patch("orggatekeeper.mo.fetch_org_unit_hierarchy_facet_uuid", new_callable=AsyncMock)
@patch(
    "orggatekeeper.mo.fetch_org_unit_hierarchy_class_uuid",
    new_callable=AsyncMock,
)
async def test_get_hidden_uuid(
    fetch_org_unit_hierarchy_class_uuid: MagicMock,
    fetch_org_unit_hierarchy_facet_uuid: MagicMock,
) -> None:
    """Test get_hidden_uuid with pre-seeded uuid."""
    facet_uuid = uuid4()
    uuid = uuid4()
    fetch_org_unit_hierarchy_facet_uuid.return_value = facet_uuid
    fetch_org_unit_hierarchy_class_uuid.return_value = uuid

    settings = get_settings(client_secret="hunter2")
    session = MagicMock()
    hidden_uuid = await get_hidden_uuid(
        session,
        hidden_uuid=settings.hidden_uuid,
        hidden_user_key=settings.hidden_user_key,
    )
    assert hidden_uuid == uuid

    fetch_org_unit_hierarchy_class_uuid.assert_called_once_with(
        session, facet_uuid, "hide"
    )
    fetch_org_unit_hierarchy_facet_uuid.assert_called_once_with(session)
