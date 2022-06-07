# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
"""Event handling."""
import asyncio
from functools import partial
from typing import Tuple

import structlog
from prometheus_client import Counter
from prometheus_client import Info
from prometheus_client import start_http_server
from ra_utils.async_to_sync import async_to_sync
from raclients.graph.client import PersistentGraphQLClient
from raclients.modelclient.mo import ModelClient
from ramqp.mo_models import MOCallbackType
from ramqp.mo_models import MORoutingKey
from ramqp.mo_models import ObjectType
from ramqp.mo_models import PayloadType
from ramqp.mo_models import RequestType
from ramqp.mo_models import ServiceType
from ramqp.moqp import MOAMQPSystem

from .calculate import update_line_management
from .config import get_settings
from .config import Settings


logger = structlog.get_logger()


update_counter = Counter(
    "orggatekeeper_changes",
    "Number of updates made",
    ["updated"],
)
build_information = Info("build_information", "Build inforomation")


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


async def organisation_gatekeeper_callback(
    gql_client: PersistentGraphQLClient,
    model_client: ModelClient,
    settings: Settings,
    mo_routing_key: MORoutingKey,
    payload: PayloadType,
) -> None:
    """Updates line management information.

    Args:
        gql_client: GraphQL client.
        model_client: MO model client.
        settings: Integration settings module.
        mo_routing_key: The message routing key.
        payload: The message payload.

    Returns:
        None
    """
    logger.debug(
        "Message received",
        service_type=mo_routing_key.service_type,
        object_type=mo_routing_key.object_type,
        request_type=mo_routing_key.request_type,
        payload=payload,
    )
    changed = await update_line_management(
        gql_client, model_client, settings, payload.uuid
    )
    update_counter.labels(updated=changed).inc()


def callback_generator(
    gql_client: PersistentGraphQLClient,
    model_client: ModelClient,
    settings: Settings,
) -> MOCallbackType:
    """Generate a line management updater callback.

    Args:
        gql_client: GraphQL client.
        model_client: MO model client.
        settings: Integration settings module.

    Returns:
        An updater callback function.
    """
    return partial(organisation_gatekeeper_callback, gql_client, model_client, settings)


def construct_clients(
    settings: Settings,
) -> Tuple[PersistentGraphQLClient, ModelClient]:
    """Construct clients froms settings.

    Args:
        settings: Integration settings module.

    Returns:
        Tuple with PersistentGraphQLClient and ModelClient.
    """
    gql_client = PersistentGraphQLClient(
        url=settings.mo_url + "/graphql",
        client_id=settings.client_id,
        client_secret=settings.client_secret.get_secret_value(),
        auth_server=settings.auth_server,
        auth_realm=settings.auth_realm,
    )
    model_client = ModelClient(
        base_url=settings.mo_url,
        client_id=settings.client_id,
        client_secret=settings.client_secret.get_secret_value(),
        auth_server=settings.auth_server,
        auth_realm=settings.auth_realm,
    )
    return gql_client, model_client


async def run_forever() -> None:  # pragma: no cover
    """Run the asyncio event-loop forever, by blocking forever.

    Returns:
        None
    """
    await asyncio.Event().wait()


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


@async_to_sync
async def main() -> None:
    """Program entrypoint.

    Starts the metrics server, then listens to AMQP messages forever.

    Returns:
        None
    """
    settings = get_settings()
    configure_logging(settings)

    logger.info("Starting metrics server", port=settings.metrics_port)
    update_build_information(
        version=settings.commit_tag, build_hash=settings.commit_sha
    )
    start_http_server(settings.metrics_port)

    logger.info("Settings up clients")
    gql_client, model_client = construct_clients(settings)

    logger.info("Settings up AMQP system")
    callback = callback_generator(gql_client, model_client, settings)

    object_types = [ObjectType.ASSOCIATION, ObjectType.ENGAGEMENT, ObjectType.ORG_UNIT]
    amqp_system = MOAMQPSystem()
    for object_type in object_types:
        amqp_system.register(ServiceType.ORG_UNIT, object_type, RequestType.WILDCARD)(
            callback
        )

    logger.info("Starting AMQP system")
    await amqp_system.start(queue_prefix=settings.queue_prefix)
    await run_forever()
    await amqp_system.stop()

    await gql_client.aclose()
    await model_client.aclose()


if __name__ == "__main__":  # pragma: no cover
    main()
