# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
"""Event handling."""

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

from .api import router as api_router
from .calculate import router as amqp_router
from .config import get_settings
from .mo import fetch_org_uuid

__all__ = ["build_information", "update_build_information"]

logger = structlog.get_logger()


@asynccontextmanager
async def _lifespan(context: Context) -> AsyncGenerator[None, None]:
    assert "legacy_graphql_session" in context
    gql_client = cast(PersistentGraphQLClient, context["legacy_graphql_session"])

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
