# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
"""Test the fetch_org_unit function."""
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=too-many-arguments
from datetime import datetime
from typing import Any
from typing import Callable
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
from ramqp.mo import PayloadType

from orggatekeeper.calculate import association_callback
from orggatekeeper.calculate import below_uuid
from orggatekeeper.calculate import engagement_callback
from orggatekeeper.calculate import fetch_org_unit
from orggatekeeper.calculate import get_class_uuid
from orggatekeeper.calculate import get_org_units_with_no_hierarchy
from orggatekeeper.calculate import get_orgunit_from_association
from orggatekeeper.calculate import get_orgunit_from_engagement
from orggatekeeper.calculate import is_line_management
from orggatekeeper.calculate import is_self_owned
from orggatekeeper.calculate import org_unit_callback
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
                            "children": [],
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
    # Assume that the unit is below the uuids given in settings.
    with patch("orggatekeeper.calculate.below_uuid", return_value=True):
        result = await is_line_management(session, uuid, set())
    assert len(params["args"]) == 2
    assert isinstance(params["args"][0], DocumentNode)
    assert params["args"][1] == {"uuids": [str(uuid)]}
    assert result == expected

    # If the unit is not below the uuids given in settings it can
    # never be line-management.
    with patch("orggatekeeper.calculate.below_uuid", return_value=False):
        result = await is_line_management(session, uuid, set())
    assert result is False


@pytest.mark.parametrize("is_children_line_management", [True, False])
async def test_is_line_management_recursion(is_children_line_management: bool) -> None:
    """Test that is_line_management is called recursively on children."""

    async def execute(*_: Any, **__: Any) -> dict[str, Any]:
        return {
            "org_units": [
                {
                    "objects": [
                        {
                            "children": [{"uuid": uuid4()}],
                        }
                    ]
                }
            ]
        }

    uuid = uuid4()
    session = MagicMock()
    session.execute = execute

    with patch(
        "orggatekeeper.calculate.check_org_unit_line_management", return_value=False
    ):
        with patch(
            "orggatekeeper.calculate.is_line_management",
            return_value=is_children_line_management,
        ):
            result = await is_line_management(
                gql_client=session, uuid=uuid, line_management_top_level_uuid=set()
            )
            assert result is is_children_line_management


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
    session = AsyncMock()
    result = await should_hide(session, uuid=uuid, enable_hide_logic=True, hidden=set())
    assert result is False


@pytest.mark.parametrize(
    "uuid,uuid_set,expected",
    [
        # Directly on top-level
        (
            UUID("0020f400-2777-4ef9-bfcb-5cdbb561d583"),
            [UUID("0020f400-2777-4ef9-bfcb-5cdbb561d583")],
            False,
        ),
        # Immediate child
        (
            UUID("8b54ca22-66cb-4f46-94ae-ee0a0c370bcf"),
            [UUID("8b54ca22-66cb-4f46-94ae-ee0a0c370bcf")],
            False,
        ),
        (
            UUID("8b54ca22-66cb-4f46-94ae-ee0a0c370bcf"),
            [UUID("58fd9427-cde0-4740-b696-31690f21f831")],
            False,
        ),
        (
            UUID("8b54ca22-66cb-4f46-94ae-ee0a0c370bcf"),
            [UUID("0020f400-2777-4ef9-bfcb-5cdbb561d583")],
            True,
        ),
        (
            UUID("8b54ca22-66cb-4f46-94ae-ee0a0c370bcf"),
            [
                UUID("8b54ca22-66cb-4f46-94ae-ee0a0c370bcf"),
                UUID("0020f400-2777-4ef9-bfcb-5cdbb561d583"),
            ],
            True,
        ),
        # Nested child
        (
            UUID("f29d62b6-4aab-44e5-95e4-be602dceaf8b"),
            [UUID("0020f400-2777-4ef9-bfcb-5cdbb561d583")],
            True,
        ),
        (
            UUID("f29d62b6-4aab-44e5-95e4-be602dceaf8b"),
            [
                UUID("8b54ca22-66cb-4f46-94ae-ee0a0c370bcf"),
                UUID("0020f400-2777-4ef9-bfcb-5cdbb561d583"),
            ],
            True,
        ),
    ],
)
async def test_below_uuid_parent(
    uuid: UUID, uuid_set: set[UUID], expected: bool
) -> None:
    """Test that below_uuid works as expected."""
    parent_map = {
        UUID("0020f400-2777-4ef9-bfcb-5cdbb561d583"): {
            "parent": None,
        },
        UUID("8b54ca22-66cb-4f46-94ae-ee0a0c370bcf"): {
            "parent": {"uuid": "0020f400-2777-4ef9-bfcb-5cdbb561d583"},
        },
        UUID("f29d62b6-4aab-44e5-95e4-be602dceaf8b"): {
            "parent": {"uuid": "8b54ca22-66cb-4f46-94ae-ee0a0c370bcf"},
        },
        UUID("58fd9427-cde0-4740-b696-31690f21f831"): {
            "parent": {"uuid": "0020f400-2777-4ef9-bfcb-5cdbb561d583"},
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
    result = await below_uuid(session, uuid, uuid_set)
    assert len(params["args"]) == 2
    assert isinstance(params["args"][0], DocumentNode)
    assert isinstance(params["args"][1], dict)
    UUID(params["args"][1]["uuids"][0])
    assert result == expected


@patch("orggatekeeper.calculate.is_line_management")
@patch("orggatekeeper.calculate.should_hide")
@patch("orggatekeeper.calculate.fetch_org_unit")
async def test_update_line_management_no_change(
    fetch_org_unit: MagicMock,
    should_hide: MagicMock,
    is_line_management: MagicMock,
    context: dict[str, Any],
    class_uuid: MagicMock,
) -> None:
    """Test that update_line_management can't do noop."""
    should_hide.return_value = False
    is_line_management.return_value = False
    # Test with top level org_unit to avoid recursive calls to update_line_management
    org_unit = OrganisationUnit.from_simplified_fields(
        user_key="AAAA",
        name="Test",
        org_unit_type_uuid=uuid4(),
        org_unit_level_uuid=uuid4(),
        parent_uuid=ORG_UUID,
        from_date=datetime.now().isoformat(),
    )
    fetch_org_unit.return_value = org_unit

    uuid = org_unit.uuid

    result = await update_line_management(**context, uuid=uuid)
    assert result is True
    gql_client = context["gql_client"]
    should_hide.assert_called_once_with(
        gql_client=gql_client, uuid=uuid, enable_hide_logic=True, hidden=set()
    )
    is_line_management.assert_called_once_with(gql_client, uuid, set())
    fetch_org_unit.assert_called_once_with(gql_client, uuid)
    model_client = context["model_client"]
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

    should_hide.return_value = True
    fetch_org_unit.return_value = org_unit

    uuid = org_unit.uuid
    result = await update_line_management(
        gql_client=gql_client,
        model_client=model_client,
        settings=settings,
        org_uuid=ORG_UUID,
        uuid=uuid,
    )
    assert result is True

    should_hide.assert_called_once_with(
        gql_client=gql_client, uuid=uuid, enable_hide_logic=True, hidden=set()
    )
    fetch_org_unit.assert_called_once_with(gql_client, uuid)
    model_client.edit.assert_not_called()


@patch("orggatekeeper.calculate.datetime")
@patch("orggatekeeper.calculate.should_hide")
@patch("orggatekeeper.calculate.fetch_org_unit")
async def test_update_line_management_hidden(
    fetch_org_unit: MagicMock,
    should_hide: MagicMock,
    mock_datetime: MagicMock,
    context: dict[str, Any],
    class_uuid: UUID,
) -> None:
    """Test that update_line_management can set class_uuid."""
    should_hide.return_value = True
    # Test with top level org_unit to avoid recursive calls to update_line_management
    org_unit = OrganisationUnit.from_simplified_fields(
        user_key="AAAA",
        name="Test",
        org_unit_type_uuid=uuid4(),
        org_unit_level_uuid=uuid4(),
        parent_uuid=ORG_UUID,
        from_date=datetime.now().isoformat(),
    )

    fetch_org_unit.return_value = org_unit

    now = datetime.now()
    mock_datetime.datetime.now.return_value = now

    uuid = org_unit.uuid
    result = await update_line_management(**context, uuid=uuid)
    assert result is True
    gql_client = context["gql_client"]

    should_hide.assert_called_once_with(
        gql_client=gql_client, uuid=uuid, enable_hide_logic=True, hidden=set()
    )
    fetch_org_unit.assert_called_once_with(gql_client, uuid)
    model_client = context["model_client"]
    assert model_client.mock_calls == [
        call.edit(
            [
                org_unit.copy(
                    update={
                        "org_unit_hierarchy": OrgUnitHierarchy(uuid=class_uuid),
                        "parent": None,
                        "validity": Validity(from_date=now.date()),
                    }
                )
            ]
        )
    ]


# pylint: disable=R0914
@pytest.mark.parametrize("should_hide_return", [True, False])
@pytest.mark.parametrize("is_line_management_return", [True, False])
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
    should_hide_return: MagicMock,
    is_line_management_return: MagicMock,
    context: dict[str, Any],
    class_uuid: UUID,
    org_unit: OrganisationUnit,
) -> None:
    """Test that update_line_management can set line_management_uuid."""
    parent_org_unit = OrganisationUnit.from_simplified_fields(
        user_key="AAAB",
        name="Test Parent",
        org_unit_type_uuid=uuid4(),
        org_unit_level_uuid=uuid4(),
        parent_uuid=ORG_UUID,
        from_date=datetime.now().isoformat(),
    )
    org_unit = OrganisationUnit.from_simplified_fields(
        user_key="AAAA",
        name="Test",
        org_unit_type_uuid=uuid4(),
        org_unit_level_uuid=uuid4(),
        parent_uuid=parent_org_unit.uuid,
        from_date=datetime.now().isoformat(),
    )
    fetch_org_unit.side_effect = [org_unit, parent_org_unit]
    org_unit_hierarchy_mock.side_effect = [
        OrgUnitHierarchy(uuid=class_uuid) if changes else org_unit.org_unit_hierarchy,
        parent_org_unit.org_unit_hierarchy,
    ]
    self_owned_it_system_check = "IT-system"

    now = datetime.now()
    mock_datetime.datetime.now.return_value = now
    uuid = org_unit.uuid

    gql_client = context["gql_client"]
    model_client = context["model_client"]
    settings = context["settings"]
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
                    "orggatekeeper.calculate.should_hide",
                    return_value=should_hide_return,
                ) as should_hide_mock:
                    result = await update_line_management(**context, uuid=uuid)

    assert result == changes

    # There are no changes to the org_unit_hierarchy, don't check the parent
    if not changes:
        # Always check if hidden
        should_hide_mock.assert_called_once_with(
            gql_client=gql_client, uuid=uuid, enable_hide_logic=True, hidden=set()
        )

        # Then check if it is line management
        if not should_hide_return:
            is_line_management_mock.assert_called_once_with(
                gql_client, uuid, settings.line_management_top_level_uuids
            )

        # Then check for self-owned
        if not (should_hide_return or is_line_management_return):
            is_self_owned_mock.assert_called_once_with(
                gql_client, uuid, self_owned_it_system_check
            )
        fetch_org_unit.assert_called_once_with(gql_client, uuid)
        assert model_client.mock_calls == []

    # If there are changes to org_unit_hierarchy, test that the parent is also checked
    else:

        assert should_hide_mock.call_count == 2
        if not should_hide_return:
            assert is_line_management_mock.call_count == 2
        if not (should_hide_return or is_line_management_return):
            assert is_self_owned_mock.call_count == 2
        # Only the org_unit, not the parent, is updated
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
@patch("orggatekeeper.calculate.fetch_org_unit")
async def test_update_line_management_line_for_root_org_unit(
    fetch_org_unit: MagicMock,
    should_hide: MagicMock,
    is_line_management: MagicMock,
    mock_datetime: MagicMock,
    context: dict[str, Any],
    class_uuid: UUID,
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
    result = await update_line_management(**context, uuid=uuid)
    assert result is True
    gql_client = context["gql_client"]
    model_client = context["model_client"]

    should_hide.assert_called_once_with(
        gql_client=gql_client, uuid=uuid, enable_hide_logic=True, hidden=set()
    )
    is_line_management.assert_called_once_with(gql_client, uuid, set())
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


async def test_get_class_uuid_preseed(mock_amqp_settings: pytest.MonkeyPatch) -> None:
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
async def test_get_class_uuid(fetch_class_uuid: MagicMock, settings: MagicMock) -> None:
    """Test get_class_uuid with pre-seeded uuid."""
    uuid = uuid4()
    fetch_class_uuid.return_value = uuid

    session = MagicMock()
    class_uuid = await get_class_uuid(
        session,
        class_uuid=settings.hidden_uuid,
        class_user_key=settings.hidden_user_key,
    )
    assert class_uuid == uuid

    fetch_class_uuid.assert_called_once_with(session, "hide")


@pytest.mark.parametrize(
    "enable_hide_logic,below_uuid_return,expected",
    [
        (True, True, True),
        (True, False, False),
        (False, True, False),
        (False, False, False),
    ],
)
async def test_should_hide(
    enable_hide_logic: bool, below_uuid_return: bool, expected: bool
) -> None:
    """Test that should hide works as expected"""
    session = AsyncMock()
    with patch("orggatekeeper.calculate.below_uuid", return_value=below_uuid_return):
        result = await should_hide(session, uuid4(), enable_hide_logic, set())
    assert result == expected


async def test_should_hide_in_settings() -> None:
    """Test that should hide works as expected"""
    session = AsyncMock()
    uuid = uuid4()
    result = await should_hide(
        session,
        uuid,
        True,
        set([uuid]),
    )
    assert result is True


async def test_line_management_for_unit_in_settings() -> None:
    """Test that a unit is marked as line management if its uuid is in settings"""
    session = AsyncMock()
    uuid = uuid4()
    result = await is_line_management(
        session,
        uuid,
        set([uuid]),
    )
    assert result is True


async def test_get_org_units_with_no_hierarchy() -> None:
    """Test the graphql call to return org_units where org_unit_hierarchy is unset"""
    gql_client = AsyncMock()
    unset_org_unit_uuids = [uuid4(), uuid4(), uuid4()]
    unset_org_units = [
        {"uuid": uuid, "objects": [{"org_unit_hierarchy": None}]}
        for uuid in unset_org_unit_uuids
    ]
    set_org_unit_uuids = [uuid4(), uuid4(), uuid4()]
    set_org_units = [
        {"uuid": uuid, "objects": [{"org_unit_hierarchy": uuid4()}]}
        for uuid in set_org_unit_uuids
    ]
    gql_client.execute.return_value = gql_client.execute.return_value = {
        "org_units": unset_org_units + set_org_units
    }
    res = await get_org_units_with_no_hierarchy(gql_client)
    assert res == unset_org_unit_uuids


async def test_get_orgunit_from_engagement() -> None:
    """Test graphql call to return org_unit from a users engagements"""
    gql_client = AsyncMock()
    expected = uuid4()
    gql_client.execute.return_value = {
        "engagements": [
            {
                "objects": [
                    {"org_unit_uuid": str(expected)},
                    {"org_unit_uuid": str(expected)},
                ]
            }
        ]
    }
    res = await get_orgunit_from_engagement(gql_client, uuid4())
    gql_client.execute.assert_called_once()
    assert res == {expected}


async def test_get_orgunit_from_association() -> None:
    """Test graphql call to return org_unit from an association"""
    gql_client = AsyncMock()
    expected = uuid4()
    gql_client.execute.return_value = {
        "associations": [
            {
                "objects": [
                    {"org_unit_uuid": str(expected)},
                    {"org_unit_uuid": str(expected)},
                ]
            }
        ]
    }
    res = await get_orgunit_from_association(gql_client, uuid4())
    gql_client.execute.assert_called_once()
    assert res == {expected}


@patch("orggatekeeper.calculate.update_line_management")
async def test_callback_engagement(
    update_line_management_mock: MagicMock, context: dict[str, Any]
) -> None:
    """Test that changes to engagements results in calls to update_line_management
    with the org_unit_uuid of an engagement.
    """
    org_unit_uuid = uuid4()
    payload = PayloadType(uuid=uuid4(), object_uuid=uuid4(), time=datetime.now())
    with patch(
        "orggatekeeper.calculate.get_orgunit_from_engagement",
        return_value={org_unit_uuid},
    ):
        await engagement_callback(context, payload=payload, _=None)
    update_line_management_mock.assert_called_once_with(**context, uuid=org_unit_uuid)


@patch("orggatekeeper.calculate.update_line_management")
async def test_callback_engagement_missing_uuid(
    update_line_management_mock: MagicMock, context: dict[str, Any]
) -> None:
    """Test that changes to engagements results in calls to update_line_management
    with the org_unit_uuid of an engagement.
    """
    payload = PayloadType(uuid=uuid4(), object_uuid=uuid4(), time=datetime.now())
    with patch(
        "orggatekeeper.calculate.get_orgunit_from_engagement",
        side_effect=ValueError,
    ):
        await engagement_callback(context, payload=payload, _=None)
    update_line_management_mock.assert_not_called()


@patch("orggatekeeper.calculate.update_line_management")
async def test_callback_association(
    update_line_management_mock: MagicMock, context: dict[str, Any]
) -> None:
    """Test that changes to associations results in calls to update_line_management
    with the org_unit_uuid of an association.
    """
    payload = PayloadType(uuid=uuid4(), object_uuid=uuid4(), time=datetime.now())
    with patch(
        "orggatekeeper.calculate.get_orgunit_from_association", return_value={uuid4()}
    ):
        await association_callback(context, payload=payload, _=None)
    update_line_management_mock.assert_called_once()


@patch("orggatekeeper.calculate.update_line_management")
async def test_callback_association_missing_uuid(
    update_line_management_mock: MagicMock, context: dict[str, Any]
) -> None:
    """Test that changes to associations results in calls to update_line_management
    with the org_unit_uuid of an association.
    """
    payload = PayloadType(uuid=uuid4(), object_uuid=uuid4(), time=datetime.now())
    with patch(
        "orggatekeeper.calculate.get_orgunit_from_association", side_effect=ValueError
    ):
        await association_callback(context, payload=payload, _=None)
    update_line_management_mock.assert_not_called()


@patch("orggatekeeper.calculate.update_line_management")
async def test_callback_org_unit(
    update_line_management_mock: MagicMock,
    context: dict[str, Any],
) -> None:
    """Test that changes calls update line management with an org_units uuid"""
    uuid = uuid4()
    payload = PayloadType(uuid=uuid, object_uuid=uuid4(), time=datetime.now())
    await org_unit_callback(context, payload=payload, _=None)
    update_line_management_mock.assert_called_once_with(**context, uuid=uuid)
