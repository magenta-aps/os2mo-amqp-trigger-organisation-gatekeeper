# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
"""Settings handling."""
from functools import cache
from typing import Any
from typing import Type
from uuid import UUID

import structlog
from pydantic import AnyHttpUrl
from pydantic import BaseSettings
from pydantic import conint
from pydantic import Field
from pydantic import parse_obj_as
from pydantic import SecretStr


Port: Type[int] = conint(ge=0, le=65535)


logger = structlog.get_logger()


class Settings(BaseSettings):
    """Settings for organisation gatekeeper.

    Note that AMQP related settings are taken directly by RAMQP:
    * https://git.magenta.dk/rammearkitektur/ramqp/-/blob/master/ramqp/config.py
    """

    # pylint: disable=too-few-public-methods

    metrics_port: Port = Field(  # type: ignore
        8011, description="Port to host Prometheus metrics on."
    )

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
    queue_prefix: str = Field(
        "os2mo-amqp-trigger-organisation-gatekeeper",
        description="The prefix to attach to queues for this program.",
    )


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
