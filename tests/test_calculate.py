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
from orggatekeeper.calculate import get_class_uuid
from orggatekeeper.calculate import is_line_management
from orggatekeeper.calculate import is_self_owned
from orggatekeeper.calculate import should_hide
from orggatekeeper.calculate import update_line_management
from orggatekeeper.config import get_settings
from orggatekeeper.config import Settings
from orggatekeeper.mo import fetch_class_uuid
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


# TODO: Test Cache of cached async methods


async def test_fetch_class_uuid() -> None:
    """Test that fetch_org_unit_hierarchy_class can find our class uuid."""
    params: dict[str, Any] = {}

    classes = {
        "key1": "24029af8-8289-4f37-9a03-efb4a06e7a29",
    }

    async def execute(*args: Any, **kwargs: Any) -> dict[str, Any]:
        params["args"] = args
        params["kwargs"] = kwargs

        return {
            "classes": [
                {
                    "uuid": value,
                    "user_key": key,
                }
                for key, value in classes.items()
            ]
        }

    for key, uuid in classes.items():
        session = MagicMock()
        session.execute = execute
        result = await fetch_class_uuid(session, key)
        assert len(params["args"]) == 2
        assert isinstance(params["args"][0], DocumentNode)
        assert params["args"][1] == {"user_keys": [key]}

        assert isinstance(result, UUID)
        assert result == UUID(uuid)


@pytest.mark.parametrize(
    "org_unit_level_user_key,num_engagements,num_assocations,expected",
    [
        (None, 0, 0, False),
        # Engagements and associations do matter with NY as well as afdelings-niveau
        # we need either engagements or assocations
        ("NY0-niveau", 0, 0, False),
        ("NY0-niveau", 42, 0, True),
        ("NY0-niveau", 0, 42, True),
        ("NY0-niveau", 42, 42, True),
        ("Afdelings-niveau", 0, 0, False),
        ("Afdelings-niveau", 42, 0, True),
        ("Afdelings-niveau", 0, 42, True),
        ("Afdelings-niveau", 42, 42, True),
        # Single digit is good
        ("NY1-niveau", 1, 0, True),
        ("NY6-niveau", 1, 0, True),
        ("NY9-niveau", 1, 0, True),
        # Double digit and negative are not
        ("NY10-niveau", 1, 0, False),
        ("NY-1-niveau", 1, 0, False),
    ],
)
async def test_is_line_management(
    org_unit_level_user_key: str | None,
    num_engagements: int,
    num_assocations: int,
    expected: bool,
) -> None:
    """Test that is_line_management works as expected."""
    params: dict[str, Any] = {}

    async def execute(*args: Any, **kwargs: Any) -> dict[str, Any]:
        params["args"] = args
        params["kwargs"] = kwargs
        return_value = {
            "org_units": [
                {
                    "objects": [
                        {
                            "user_key": "dummy_user_key",
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
        if org_unit_level_user_key is None:
            del return_value["org_units"][0]["objects"][0]["org_unit_level"]
        return return_value

    uuid = uuid4()
    session = MagicMock()
    session.execute = execute
    result = await is_line_management(session, uuid, [])
    assert len(params["args"]) == 2
    assert isinstance(params["args"][0], DocumentNode)
    assert params["args"][1] == {"uuids": [str(uuid)]}
    assert result == expected


@pytest.mark.parametrize("expected", [True, False])
async def test_is_self_owned(expected: bool) -> None:
    """Test check for self-owned"""
    params: dict[str, Any] = {}
    it_system_uuid = uuid4()

    async def execute(*args: Any, **kwargs: Any) -> dict[str, Any]:
        params["args"] = args
        params["kwargs"] = kwargs
        return {
            "org_units": [
                {
                    "objects": [
                        {
                            "itusers": [
                                {
                                    "itsystem_uuid": str(it_system_uuid)
                                    if expected
                                    else str(uuid4())
                                }
                            ]
                        }
                    ]
                }
            ]
        }

    uuid = uuid4()
    session = MagicMock()
    session.execute = execute
    with patch(
        "orggatekeeper.calculate.get_it_system_uuid", return_value=it_system_uuid
    ):
        result = await is_self_owned(session, uuid=uuid, check_it_system_name="test")
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
            "parent": None,
        },
        UUID("8b54ca22-66cb-4f46-94ae-ee0a0c370bcf"): {
            "user_key": "AAAB",
            "parent": {"uuid": UUID("0020f400-2777-4ef9-bfcb-5cdbb561d583")},
        },
        UUID("f29d62b6-4aab-44e5-95e4-be602dceaf8b"): {
            "user_key": "AAAC",
            "parent": {"uuid": UUID("8b54ca22-66cb-4f46-94ae-ee0a0c370bcf")},
        },
        UUID("58fd9427-cde0-4740-b696-31690f21f831"): {
            "user_key": "AABA",
            "parent": {"uuid": UUID("0020f400-2777-4ef9-bfcb-5cdbb561d583")},
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

    def setup_mock_settings(*args: Any, **kwargs: Any) -> Settings:
        settings = get_settings(client_secret="hunter2", *args, **kwargs)
        return settings

    yield setup_mock_settings


@pytest.fixture()
def settings(set_settings: Callable[..., Settings]) -> Generator[Settings, None, None]:
    """Fixture to mock get_settings."""
    yield set_settings()


@pytest.fixture()
def class_uuid(
    gql_client: MagicMock, settings: Settings
) -> Generator[UUID, None, None]:
    """Fixture to mock get_class_uuid."""
    with patch("orggatekeeper.calculate.get_class_uuid") as get_class_uuid:
        class_uuid = uuid4()
        get_class_uuid.return_value = class_uuid
        yield class_uuid


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
@patch("orggatekeeper.calculate.below_user_key")
@patch("orggatekeeper.calculate.fetch_org_unit")
async def test_update_line_management_no_change(
    fetch_org_unit: MagicMock,
    below_user_key: MagicMock,
    should_hide: MagicMock,
    is_line_management: MagicMock,
    gql_client: MagicMock,
    model_client: AsyncMock,
    seeded_update_line_management: Callable[[UUID], Awaitable[bool]],
    class_uuid: MagicMock,
    org_unit: OrganisationUnit,
) -> None:
    """Test that update_line_management can't do noop."""
    should_hide.return_value = False
    is_line_management.return_value = False
    fetch_org_unit.return_value = org_unit

    uuid = org_unit.uuid
    result = await seeded_update_line_management(uuid)
    assert result is True

    should_hide.assert_called_once_with(gql_client, uuid, [])
    is_line_management.assert_called_once_with(gql_client, uuid, [])
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
    class_uuid: MagicMock,
    org_unit: OrganisationUnit,
) -> None:
    """Test that update_line_management can set class_uuid."""
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
    class_uuid: UUID,
    seeded_update_line_management: Callable[[UUID], Awaitable[bool]],
    org_unit: OrganisationUnit,
) -> None:
    """Test that update_line_management can set class_uuid."""
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
                        "org_unit_hierarchy": OrgUnitHierarchy(uuid=class_uuid),
                        "validity": Validity(from_date=now.date()),
                    }
                )
            ]
        )
    ]


# pylint: disable=R0914
@pytest.mark.parametrize("should_hide_return", [True, False])
@pytest.mark.parametrize("is_line_management_return", [True, False])
@pytest.mark.parametrize("below_user_key_return", [True, False])
@pytest.mark.parametrize("is_self_owned_return", [True, False])
@pytest.mark.parametrize("changes", [True, False])
@patch("orggatekeeper.calculate.datetime")
@patch("orggatekeeper.calculate.fetch_org_unit")
@patch("orggatekeeper.calculate.OrgUnitHierarchy")
async def test_update_line_management_line(
    org_unit_hierarchy_mock: MagicMock,
    fetch_org_unit: MagicMock,
    mock_datetime: MagicMock,
    changes: bool,
    is_self_owned_return: MagicMock,
    below_user_key_return: MagicMock,
    is_line_management_return: MagicMock,
    should_hide_return: MagicMock,
    gql_client: MagicMock,
    model_client: AsyncMock,
    settings: Settings,
    class_uuid: UUID,
    seeded_update_line_management: Callable[[UUID], Awaitable[bool]],
    org_unit: OrganisationUnit,
) -> None:
    """Test that update_line_management can set line_management_uuid."""
    fetch_org_unit.return_value = org_unit
    org_unit_hierarchy_mock.return_value = (
        OrgUnitHierarchy(uuid=class_uuid) if changes else org_unit.org_unit_hierarchy
    )
    self_owned_it_system_check = "IT-system"

    now = datetime.now()
    mock_datetime.datetime.now.return_value = now
    uuid = org_unit.uuid
    settings.self_owned_it_system_check = self_owned_it_system_check

    with patch(
        "orggatekeeper.calculate.is_line_management",
        return_value=is_line_management_return,
    ) as is_line_management_mock:
        with patch(
            "orggatekeeper.calculate.is_self_owned", return_value=is_self_owned_return
        ) as is_self_owned_mock:
            with patch(
                "orggatekeeper.calculate.should_hide", return_value=should_hide_return
            ) as should_hide_mock:
                with patch(
                    "orggatekeeper.calculate.below_user_key",
                    return_value=below_user_key_return,
                ) as below_user_key_mock:
                    result = await seeded_update_line_management(uuid)

    assert result == changes

    # Always check if hidden
    should_hide_mock.assert_called_once_with(gql_client, uuid, [])

    # Then check if below main line management unit if it isn't hidden
    if not should_hide_return:
        below_user_key_mock.assert_called_once_with(gql_client, uuid, [])

    if not should_hide_return and below_user_key_return:
        is_line_management_mock.assert_called_once_with(gql_client, uuid, [])

    # Then check for self-owned
    if not (should_hide_return or is_line_management_return):
        is_self_owned_mock.assert_called_once_with(
            gql_client, uuid, self_owned_it_system_check
        )
    fetch_org_unit.assert_called_once_with(gql_client, uuid)
    if not changes:
        assert model_client.mock_calls == []
    else:
        assert model_client.mock_calls == [
            call.edit(
                [
                    org_unit.copy(
                        update={
                            "org_unit_hierarchy": OrgUnitHierarchy(uuid=class_uuid),
                            "validity": Validity(from_date=now.date()),
                        }
                    )
                ]
            )
        ]


@patch("orggatekeeper.calculate.datetime")
@patch("orggatekeeper.calculate.is_line_management")
@patch("orggatekeeper.calculate.should_hide")
@patch("orggatekeeper.calculate.below_user_key")
@patch("orggatekeeper.calculate.fetch_org_unit")
async def test_update_line_management_line_for_root_org_unit(
    fetch_org_unit: MagicMock,
    below_user_key: MagicMock,
    should_hide: MagicMock,
    is_line_management: MagicMock,
    mock_datetime: MagicMock,
    gql_client: MagicMock,
    model_client: AsyncMock,
    settings: Settings,
    class_uuid: UUID,
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
        from_date=datetime.now().isoformat(),
    )
    fetch_org_unit.return_value = org_unit

    now = datetime.now()
    mock_datetime.datetime.now.return_value = now

    uuid = org_unit.uuid
    result = await seeded_update_line_management(uuid)
    assert result is True

    should_hide.assert_called_once_with(gql_client, uuid, [])
    is_line_management.assert_called_once_with(gql_client, uuid, [])
    fetch_org_unit.assert_called_once_with(gql_client, uuid)
    assert model_client.mock_calls == [
        call.edit(
            [
                org_unit.copy(
                    update={
                        "org_unit_hierarchy": OrgUnitHierarchy(uuid=class_uuid),
                        "parent": None,  # Since the unit is a root org unit
                        "validity": Validity(from_date=now.date()),
                    }
                )
            ]
        )
    ]


async def test_get_class_uuid_preseed() -> None:
    """Test get_class_uuid with pre-seeded uuid."""
    uuid = uuid4()
    settings = get_settings(
        client_secret="hunter2",
        hidden_uuid=uuid,
    )
    session = MagicMock()
    class_uuid = await get_class_uuid(
        session,
        class_uuid=settings.hidden_uuid,
        class_user_key=settings.hidden_user_key,
    )
    assert class_uuid == uuid


@patch(
    "orggatekeeper.mo.fetch_class_uuid",
    new_callable=AsyncMock,
)
async def test_get_class_uuid(
    fetch_class_uuid: MagicMock,
) -> None:
    """Test get_class_uuid with pre-seeded uuid."""
    uuid = uuid4()
    fetch_class_uuid.return_value = uuid

    settings = get_settings(client_secret="hunter2")
    session = MagicMock()
    class_uuid = await get_class_uuid(
        session,
        class_uuid=settings.hidden_uuid,
        class_user_key=settings.hidden_user_key,
    )
    assert class_uuid == uuid

    fetch_class_uuid.assert_called_once_with(session, "hide")
