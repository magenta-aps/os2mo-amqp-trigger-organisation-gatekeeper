# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
"""FastRAMQPI Context."""
from typing import Any
from typing import AsyncContextManager
from typing import Awaitable
from typing import Callable
from typing import TypedDict

from fastapi import FastAPI
from gql.client import AsyncClientSession
from raclients.graph.client import GraphQLClient
from raclients.modelclient.mo import ModelClient
from ramqp.mo import MOAMQPSystem

from .config import Settings


HealthcheckFunction = Callable[["Context"], Awaitable[bool]]  # type: ignore


class Context(TypedDict, total=False):
    """Execution context."""

    name: str
    settings: Settings
    healthchecks: dict[str, HealthcheckFunction]  # type: ignore
    lifespan_managers: dict[int, set[AsyncContextManager]]
    app: FastAPI
    amqpsystem: MOAMQPSystem
    graphql_client: GraphQLClient
    graphql_session: AsyncClientSession
    model_client: ModelClient
    user_context: dict[str, Any]
