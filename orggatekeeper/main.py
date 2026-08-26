# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
"""Event handling."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any
from typing import cast

import structlog
from fastapi import FastAPI
from fastramqpi.app import build_information
from fastramqpi.app import update_build_information
from fastramqpi.context import Context
from fastramqpi.main import FastRAMQPI
from fastramqpi.raclients.graph.client import PersistentGraphQLClient
from fastramqpi.raclients.modelclient.mo import ModelClient

from .api import router as api_router
from .calculate import router as amqp_router
from .config import Settings
from .config import get_settings
from .mo import fetch_org_uuid

__all__ = ["build_information", "update_build_information"]

logger = structlog.get_logger()


def construct_clients(
    settings: Settings,
) -> tuple[PersistentGraphQLClient, ModelClient]:
    """Construct clients froms settings.

    Args:
        settings: Integration settings module.

    Returns:
        Tuple with PersistentGraphQLClient and ModelClient.
    """
    gql_client = PersistentGraphQLClient(
        url=settings.fastramqpi.mo_url + "/graphql/v22",
        client_id=settings.fastramqpi.client_id,
        client_secret=settings.fastramqpi.client_secret.get_secret_value(),
        auth_server=settings.fastramqpi.auth_server,
        auth_realm=settings.fastramqpi.auth_realm,
        execute_timeout=settings.fastramqpi.graphql_timeout,
        httpx_client_kwargs={"timeout": settings.fastramqpi.graphql_timeout},
    )
    model_client = ModelClient(
        base_url=settings.fastramqpi.mo_url,
        client_id=settings.fastramqpi.client_id,
        client_secret=settings.fastramqpi.client_secret.get_secret_value(),
        auth_server=settings.fastramqpi.auth_server,
        auth_realm=settings.fastramqpi.auth_realm,
    )
    return gql_client, model_client


def configure_logging(settings: Settings) -> None:
    """Setup our logging.

    Args:
        settings: Integration settings module.

    Returns:
        None
    """
    log_level = getattr(logging, settings.fastramqpi.log_level.upper(), logging.INFO)
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(log_level))


def construct_context() -> dict[str, Any]:
    """Construct request context."""
    return {}


@asynccontextmanager
async def _lifespan(context: Context) -> AsyncGenerator[None, None]:
    gql_client = cast(PersistentGraphQLClient, ["legacy_graphql_client"])

    assert "user_context" in context
    user_context = context["user_context"]
    user_context["org_uuid"] = await fetch_org_uuid(gql_client)
    yield


def create_app(  # pylint: disable=too-many-statements
    *args: Any, **kwargs: Any
) -> FastAPI:
    """FastAPI application factory.

    Starts the metrics server, then listens to AMQP messages forever.

    Returns:
        None
    """
    settings = get_settings(*args, **kwargs)

    fastramqpi = FastRAMQPI(
        application_name="orggatekeeper",
        settings=settings.fastramqpi,
        graphql_version=22,
    )

    fastramqpi.add_context(settings=settings)
    fastramqpi.get_amqpsystem().router.registry.update(amqp_router.registry)
    fastramqpi.add_lifespan_manager(_lifespan(fastramqpi.get_context()), priority=350)

    app = fastramqpi.get_app()
    app.include_router(api_router)

    return app
