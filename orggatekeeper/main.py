# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
"""Event handling."""
import structlog
from prometheus_client import Counter
from prometheus_client import start_http_server
from ramqp.mo_models import ObjectType
from ramqp.mo_models import PayloadType
from ramqp.mo_models import RequestType
from ramqp.mo_models import ServiceType
from ramqp.moqp import MOAMQPSystem

from .calculate import update_line_management
from .config import get_settings

update_counter = Counter(
    "orggatekeeper_changes",
    "Number of updates made",
    ["updated"],
)

logger = structlog.get_logger()


async def organisation_gatekeeper_callback(
    service_type: ServiceType,
    object_type: ObjectType,
    request_type: RequestType,
    payload: PayloadType,
) -> None:
    """Updates line management information.

    Args:
        service_type: The service type to send the message to.
        object_type: The object type to send the message to.
        request_type: The request type to send the message to.
        payload: The message payload.

    Returns:
        None
    """
    logger.debug(
        "Message received",
        service_type=service_type,
        object_type=object_type,
        request_type=request_type,
        payload=payload,
    )
    changed = await update_line_management(payload.uuid)
    update_counter.labels(updated=changed).inc()


def main() -> None:
    """Program entrypoint.

    Starts the metrics server, then listens to AMQP messages forever.

    Returns:
        None
    """
    settings = get_settings()

    logger.info("Starting metrics server", port=settings.metrics_port)
    start_http_server(settings.metrics_port)

    amqp_system = MOAMQPSystem()
    # TODO: Also need to listen to engagements and associations
    # Otherwise we will not recognize people being added via engagements, etc.
    amqp_system.register(
        ServiceType.ORG_UNIT, ObjectType.ORG_UNIT, RequestType.WILDCARD
    )(organisation_gatekeeper_callback)

    logger.info("Starting AMQP system")
    amqp_system.run_forever(queue_prefix=settings.queue_prefix)


if __name__ == "__main__":  # pragma: no cover
    main()
