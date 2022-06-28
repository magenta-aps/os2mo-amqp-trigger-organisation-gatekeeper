# SPDX-FileCopyrightText: 2021 Magenta ApS <https://magenta.dk>
# SPDX-License-Identifier: MPL-2.0
"""Settings handling."""
from pydantic import AnyHttpUrl
from pydantic import BaseSettings
from pydantic import Field
from pydantic import parse_obj_as
from pydantic import SecretStr
from ramqp.config import ConnectionSettings


# pylint: disable=too-few-public-methods
class Settings(BaseSettings):
    """Settings for the FastRAMQPI framework."""

    class Config:
        """Settings are frozen."""

        frozen = True
        env_nested_delimiter = "__"

    amqp: ConnectionSettings = Field(
        ConnectionSettings(), description="AMQP connection settings"
    )

    commit_tag: str = Field("HEAD", description="Git commit tag.")
    commit_sha: str = Field("HEAD", description="Git commit SHA.")

    log_level: str = Field("INFO", description="Log level to configure.")

    enable_metrics: bool = Field(True, description="Whether to enable metrics.")

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
    graphql_timeout: int = 120
