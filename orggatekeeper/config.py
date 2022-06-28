# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
"""Settings handling."""
from functools import cache
from typing import Any
from uuid import UUID

import structlog
from pydantic import BaseSettings
from pydantic import Field

from fastramqpi.config import Settings as FastRAMQPISettings


logger = structlog.get_logger()


# pylint: disable=too-few-public-methods
class Settings(BaseSettings):
    """Settings for organisation gatekeeper."""

    class Config:
        """Settings are frozen."""

        frozen = True
        env_nested_delimiter = "__"

    fastramqpi: FastRAMQPISettings = Field(
        default_factory=FastRAMQPISettings, description="FastRAMQPI settings"
    )

    enable_hide_logic = Field(True, description="Whether or not to enable hide logic.")
    hidden: list[str] = Field(
        [],
        description="List of organisation-unit user-keys to hide (childrens included).",
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

    dry_run: bool = Field(
        False, description="Run in dry-run mode, only printing what would have changed."
    )


@cache
def get_settings(**kwargs: Any) -> Settings:
    """Fetch settings object.

    Args:
        kwargs: overrides

    Return:
        Cached settings object.
    """
    settings = Settings(**kwargs)
    logger.debug("Settings fetched", settings=settings, kwargs=kwargs)
    return settings
