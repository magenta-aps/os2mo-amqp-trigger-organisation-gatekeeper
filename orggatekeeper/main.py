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
        url=settings.mo_url + "/graphql/v22",
        client_id=settings.client_id,
        client_secret=settings.client_secret.get_secret_value(),
        auth_server=settings.auth_server,
        auth_realm=settings.auth_realm,
        execute_timeout=settings.graphql_timeout,
        httpx_client_kwargs={"timeout": settings.graphql_timeout},
    )
    model_client = ModelClient(
        base_url=settings.mo_url,
        client_id=settings.client_id,
        client_secret=settings.client_secret.get_secret_value(),
        auth_server=settings.auth_server,
        auth_realm=settings.auth_realm,
    )
    return gql_client, model_client


def configure_logging(settings: Settings) -> None:
    """Setup our logging.

    Args:
        settings: Integration settings module.

    Returns:
        None
    """
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(settings.log_level.value)
    )


def construct_context() -> dict[str, Any]:
    """Construct request context."""
    return {}


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
        version=settings.commit_tag, build_hash=settings.commit_sha
    )
    if settings.expose_metrics:
        Instrumentator().instrument(app).expose(app)

    context = construct_context()

    # TODO(#70974): this is only needed temporarily, to make the git history
    #   more clean. Context will be handled by FastRAMQPI in a later commit.
    app.state.context = context

    # pylint: disable=unused-argument
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator:
        async with AsyncExitStack() as stack:
            logger.info("Settings up clients")
            gql_client, model_client = construct_clients(settings)
            context["settings"] = settings

            context["model_client"] = await stack.enter_async_context(model_client)
            context["gql_client"] = await stack.enter_async_context(gql_client)

            # Get organisation UUID
            context["org_uuid"] = await fetch_org_uuid(gql_client)
            amqp_system = MOAMQPSystem(
                settings=settings.amqp, router=router, context=context
            )

            context["amqp_system"] = amqp_system

            logger.info("Starting AMQP system")
            await stack.enter_async_context(amqp_system)

            # Yield to keep the AMQP system open until the ASGI application is closed.
            # Control will be returned to here when the ASGI application is shut down.
            yield

    app.router.lifespan_context = lifespan
    app.include_router(api_router)

    return app
