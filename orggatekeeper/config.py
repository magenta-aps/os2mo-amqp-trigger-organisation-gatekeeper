# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
# pylint: disable=too-few-public-methods,missing-class-docstring
"""Settings handling."""
import logging
from enum import Enum
from functools import cache
from typing import Any
from uuid import UUID

import structlog
from pydantic import AnyHttpUrl
from pydantic import BaseSettings
from pydantic import Field
from pydantic import parse_obj_as
from pydantic import SecretStr
from ramqp.config import AMQPConnectionSettings


class LogLevel(Enum):
    """Log levels."""

    NOTSET = logging.NOTSET
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


logger = structlog.get_logger()


class OrgGatekeeperConnectionSettings(AMQPConnectionSettings):
    queue_prefix: str = "os2mo-amqp-trigger-organisation-gatekeeper"
    # TODO: Ensure we don't crash MO when running somewhat concurrently
    prefetch_count: int = 1


class Settings(BaseSettings):
    """Settings for organisation gatekeeper.

    Note that AMQP related settings are taken directly by RAMQP:
    * https://git.magenta.dk/rammearkitektur/ramqp/-/blob/master/ramqp/config.py
    """

    amqp: OrgGatekeeperConnectionSettings = Field(
        default_factory=OrgGatekeeperConnectionSettings  # type: ignore
    )

    commit_tag: str = Field("HEAD", description="Git commit tag.")
    commit_sha: str = Field("HEAD", description="Git commit SHA.")

    mo_url: AnyHttpUrl = Field(
        parse_obj_as(AnyHttpUrl, "http://mo-service:5000"),
        description="Base URL for OS2mo.",
    )
    client_id: str = Field("orggatekeeper", description="Client ID for OIDC client.")
    client_secret: SecretStr = Field(..., description="Client Secret for OIDC client.")
    auth_server: AnyHttpUrl = Field(
        parse_obj_as(AnyHttpUrl, "http://keycloak-service:8080/auth"),
        description="Base URL for OIDC server (Keycloak).",
    )
    auth_realm: str = Field("mo", description="Realm to authenticate against")

    sentry_dsn: str | None = None

    enable_hide_logic: bool = Field(
        True, description="Whether or not to enable hide logic."
    )
    hidden: set[UUID] = Field(
        set(),
        description="Set of organisation-unit uuids to hide (childrens included).",
    )
    hidden_uuid: UUID | None = Field(
        None,
        description=(
            "UUID of the class within the org_unit_hierarchy facet that indicates"
            " hidden."
        ),
    )
    hidden_user_key: str = Field(
        "hide",
        description=(
            "User-key of the class within the org_unit_hierarchy facet that indicates"
            " hidden, only used if hidden_uuid is not set."
        ),
    )

    line_management_uuid: UUID | None = Field(
        None,
        description=(
            "UUID of the class within the org_unit_hierarchy facet that indicates line"
            " management."
        ),
    )
    line_management_user_key: str = Field(
        "linjeorg",
        description=(
            "User-key of the class within the org_unit_hierarchy facet that indicates"
            " line management, only used if line_management_uuid is not set."
        ),
    )
    self_owned_uuid: UUID | None = Field(
        None,
        description=(
            "UUID of the class within the org_unit_hierarchy facet that indicates self-"
            " owned organisation"
        ),
    )
    self_owned_user_key: str = Field(
        "selvejet",
        description=(
            "User-key of the class within the org_unit_hierarchy facet that indicates"
            " self-owned organisation units, only used if self_owned_uuid is not set."
        ),
    )
    self_owned_it_system_check: str | None = Field(
        description=(
            "User_key of the it-system used to check whether to mark the unit as"
            " self-owned."
        )
    )

    dry_run: bool = Field(
        False, description="Run in dry-run mode, only printing what would have changed."
    )

    log_level: LogLevel = LogLevel.INFO

    expose_metrics: bool = Field(True, description="Whether to expose metrics.")

    graphql_timeout: int = 120

    line_management_top_level_uuids: set[UUID] = Field(
        set(),
        description="set of uuids of the top organisation units in line management.",
    )

    class Config:
        env_nested_delimiter = "__"  # allows setting e.g. AMQP__QUEUE_PREFIX=foo


@cache
def get_settings(*args: Any, **kwargs: Any) -> Settings:
    """Fetch settings object.

    Args:
        args: overrides
        kwargs: overrides

    Return:
        Cached settings object.
    """
    settings = Settings(*args, **kwargs)
    logger.debug("Settings fetched", settings=settings, args=args, kwargs=kwargs)
    return settings
