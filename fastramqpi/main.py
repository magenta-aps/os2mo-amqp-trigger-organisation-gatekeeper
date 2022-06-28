# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
"""FastAPI + RAMQP Framework."""
import logging
from contextlib import asynccontextmanager
from contextlib import AsyncExitStack
from functools import partial
from typing import Any
from typing import AsyncContextManager
from typing import AsyncGenerator
from typing import cast

import structlog
from fastapi import APIRouter
from fastapi import FastAPI
from fastapi import Request
from fastapi import Response
from prometheus_client import Info
from prometheus_fastapi_instrumentator import Instrumentator
from raclients.graph.client import GraphQLClient
from raclients.modelclient.mo import ModelClient
from ramqp.mo import MOAMQPSystem
from starlette.status import HTTP_204_NO_CONTENT
from starlette.status import HTTP_503_SERVICE_UNAVAILABLE

from .config import Settings
from .context import Context
from .context import HealthcheckFunction
from .healthcheck import healthcheck_gql
from .healthcheck import healthcheck_model_client


logger = structlog.get_logger()
fastapi_router = APIRouter()
build_information = Info("build_information", "Build information")


def update_build_information(version: str, build_hash: str) -> None:
    """Update build information.

    Args:
        version: The version to set.
        build_hash: The build hash to set.

    Returns:
        None.
    """
    build_information.info(
        {
            "version": version,
            "hash": build_hash,
        }
    )


def configure_logging(log_level_name: str) -> None:
    """Setup our logging.

    Args:
        log_level_name: The logging level.

    Returns:
        None
    """
    log_level_value = logging.getLevelName(log_level_name)
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(log_level_value)
    )


@fastapi_router.get("/")
async def index(request: Request) -> dict[str, str]:
    """Endpoint to return name of integration."""
    context: dict[str, Any] = request.app.state.context
    return {"name": context["name"]}


@fastapi_router.get("/health/live", status_code=HTTP_204_NO_CONTENT)
async def liveness() -> None:
    """Endpoint to be used as a liveness probe for Kubernetes."""
    return None


@fastapi_router.get(
    "/health/ready",
    status_code=HTTP_204_NO_CONTENT,
    responses={
        "204": {"description": "Ready"},
        "503": {"description": "Not ready"},
    },
)
async def readiness(request: Request, response: Response) -> Response:
    """Endpoint to be used as a readiness probe for Kubernetes."""
    response.status_code = HTTP_204_NO_CONTENT

    context: dict[str, Any] = request.app.state.context
    healthchecks = context["healthchecks"]
    all_ready = True
    try:
        for name, healthcheck in healthchecks.items():
            ready = await healthcheck(context)
            if not ready:
                logger.warn(f"{name} is not ready")
                all_ready = False
    except Exception:  # pylint: disable=broad-except
        logger.exception("Exception occured during readiness probe")
        response.status_code = HTTP_503_SERVICE_UNAVAILABLE

    if not all_ready:
        response.status_code = HTTP_503_SERVICE_UNAVAILABLE

    return response


def construct_clients(
    settings: Settings,
) -> tuple[GraphQLClient, ModelClient]:
    """Construct clients froms settings.

    Args:
        settings: Integration settings module.

    Returns:
        Tuple with PersistentGraphQLClient and ModelClient.
    """
    client_kwargs = dict(
        client_id=settings.client_id,
        client_secret=settings.client_secret.get_secret_value(),
        auth_realm=settings.auth_realm,
        auth_server=settings.auth_server,
    )

    gql_client = GraphQLClient(
        url=settings.mo_url + "/graphql",
        execute_timeout=settings.graphql_timeout,
        httpx_client_kwargs={"timeout": settings.graphql_timeout},
        **client_kwargs,
    )
    model_client = ModelClient(
        base_url=settings.mo_url,
        **client_kwargs,
    )
    return gql_client, model_client


@asynccontextmanager
async def _lifespan(context: Context) -> AsyncGenerator[None, None]:
    """ASGI lifespan context handler.

    Runs all the configured lifespan managers according to their priority.

    Returns:
        None
    """
    async with AsyncExitStack() as stack:
        lifespan_managers = context["lifespan_managers"]
        for _, priority_set in sorted(lifespan_managers.items()):
            for lifespan_manager in priority_set:
                await stack.enter_async_context(lifespan_manager)
        # Yield to keep lifespan managers open until the ASGI application is shutdown.
        yield


class FastRAMQPI:
    """FastRAMQPI (FastAPI + RAMQP) combined-system.

    Motivated by a lot a shared code between our AMQP integrations.
    """

    def __init__(self, application_name: str, settings: Settings | None = None) -> None:
        super().__init__()
        if settings is None:
            settings = Settings()
        configure_logging(settings.log_level)

        # Update metrics info
        update_build_information(
            version=settings.commit_tag, build_hash=settings.commit_sha
        )

        # Setup shared context
        self._context: Context = {
            "name": application_name,
            "settings": settings,
            "healthchecks": {},
            "lifespan_managers": {},
            "user_context": {},
        }

        # Setup FastAPI
        app = FastAPI()
        app.include_router(fastapi_router)
        app.state.context = self._context
        app.router.lifespan_context = partial(_lifespan, self._context)
        # Expose Metrics
        if settings.enable_metrics:
            Instrumentator().instrument(app).expose(app)
        self.app = app
        self._context["app"] = self.app

        # Setup AMQPSystem
        amqp_settings = settings.amqp.copy(update={"queue_prefix": application_name})
        self.amqpsystem = MOAMQPSystem(settings=amqp_settings, context=self._context)
        # Let AMQPSystems lifespan follow ASGI lifespan
        self.add_lifespan_manager(self.amqpsystem)

        async def healthcheck_amqp(context: Context) -> bool:
            """AMQP Healthcheck wrapper.

            Args:
                context: unused context dict.

            Returns:
                Whether the AMQPSystem is OK.
            """
            amqpsystem = context["amqpsystem"]
            return cast(bool, amqpsystem.healthcheck())

        self.add_healthcheck(name="AMQP", healthcheck=healthcheck_amqp)
        self._context["amqpsystem"] = self.amqpsystem

        # Prepare clients
        graphql_client, model_client = construct_clients(settings)
        # Check and expose GraphQL connection (gql_client)
        self.add_healthcheck("GraphQL", healthcheck_gql)
        self._context["graphql_client"] = graphql_client

        @asynccontextmanager
        async def graphql_session(context: Context) -> AsyncGenerator[None, None]:
            async with context["graphql_client"] as session:
                context["graphql_session"] = session
                yield

        self.add_lifespan_manager(
            cast(AsyncContextManager, partial(graphql_session, self._context))
        )
        # Check and expose Service API connection (model_client)
        self.add_lifespan_manager(model_client)
        self.add_healthcheck("Service API", healthcheck_model_client)
        self._context["model_client"] = model_client

    def add_lifespan_manager(
        self, manager: AsyncContextManager, priority: int = 1000
    ) -> None:
        """Add the provided life-cycle manager to the ASGI lifespan context.

        Args:
            manager: The manager to add.
            priority: The priority of the manager, lowest priorities are run first.

        Returns:
            None
        """

        priority_set = self._context["lifespan_managers"].setdefault(priority, set())
        priority_set.add(manager)

    def add_healthcheck(self, name: str, healthcheck: HealthcheckFunction) -> None:
        """Add the provided healthcheck to the Kubernetes readiness probe.

        Args:
            name: Name of the healthcheck to add.
            healthcheck: The healthcheck callback function.

        Raises:
            ValueError: If the name has already been used.

        Returns:
            None
        """
        if "name" in self._context["healthchecks"]:
            raise ValueError("Name already used")
        self._context["healthchecks"][name] = healthcheck

    def add_context(self, **kwargs: Any) -> None:
        """Add the provided key-value pair to the user-context.

        The added key-value pair will be available under context["user_context"].

        Args:
            key: The key to add under.
            value: The value to add.

        Returns:
            None
        """
        self._context["user_context"].update(**kwargs)

    def get_app(self) -> FastAPI:
        """Return the contained FastAPI application.

        Returns:
            FastAPI application.
        """
        return self.app

    def get_amqpsystem(self) -> MOAMQPSystem:
        """Return the contained MOAMQPSystem.

        Returns:
            MOAQMPSystem.
        """
        return self.amqpsystem
