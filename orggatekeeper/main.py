# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
"""Event handling."""

from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI
from fastramqpi.app import build_information
from fastramqpi.app import update_build_information
from fastramqpi.raclients.graph.client import PersistentGraphQLClient
from fastramqpi.raclients.modelclient.mo import ModelClient
from fastramqpi.ramqp.mo import MOAMQPSystem
from prometheus_fastapi_instrumentator import Instrumentator

from .api import router as api_router
from .calculate import UserContextDict
from .calculate import router
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
    log_level = settings.fastramqpi.log_level
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(log_level))


def construct_context() -> dict[str, Any]:
    """Construct request context."""
    return {}


@asynccontextmanager
async def _lifespan(
    settings: Settings, context: dict[str, Any]
) -> AsyncGenerator[None, None]:
    """ASGI lifespan context manager.

    Sets up clients, fetches the organisation UUID and starts the AMQP system,
    populating the provided context. Tears everything down on exit.

    Args:
        settings: Integration settings.
        context: The shared context dict to populate.

    Yields:
        None
    """
    async with AsyncExitStack() as stack:
        logger.info("Settings up clients")
        gql_client, model_client = construct_clients(settings)

        user_context: UserContextDict = {
            "settings": settings,
            "org_uuid": await fetch_org_uuid(gql_client),
        }
        context["user_context"] = user_context
        context["legacy_model_client"] = await stack.enter_async_context(model_client)
        context["legacy_graphql_session"] = await stack.enter_async_context(gql_client)

        amqp_system = MOAMQPSystem(
            settings=settings.fastramqpi.amqp, router=router, context=context
        )

        context["amqp_system"] = amqp_system

        logger.info("Starting AMQP system")
        await stack.enter_async_context(amqp_system)

        # Yield to keep the AMQP system open until the ASGI application is closed.
        # Control will be returned to here when the ASGI application is shut down.
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
    configure_logging(settings)

    app = FastAPI()

    logger.info("Starting metrics server")
    update_build_information(
        version=settings.fastramqpi.commit_tag,
        build_hash=settings.fastramqpi.commit_sha,
    )
    if settings.fastramqpi.enable_metrics:
        Instrumentator().instrument(app).expose(app)

    context = construct_context()

    # TODO(#70974): this is only needed temporarily, to make the git history
    #   more clean. Context will be handled by FastRAMQPI in a later commit.
    app.state.context = context

    # pylint: disable=unused-argument
    @asynccontextmanager
    async def app_lifespan(app: FastAPI) -> AsyncGenerator:
        async with _lifespan(settings, context):
            yield

    app.router.lifespan_context = app_lifespan
    app.include_router(api_router)

    return app
