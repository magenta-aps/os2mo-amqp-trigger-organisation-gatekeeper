<!--
SPDX-FileCopyrightText: 2021 Magenta ApS <https://magenta.dk>
SPDX-License-Identifier: MPL-2.0
-->

# Organisation Gatekeeper

This repository contains an OS2mo AMQP Trigger that updates line management information.

An organisation is part of line management iff:
* The SD unit-level is NY{x}-niveau or
* The SD unit-level is Afdelings-niveau and people are attached to it.

Additionally this function also hides organisation units iff:
* Their user-key is contained within hidden_user_key or a child of it.

If an organisation unit is not part of line management but has an it-account in a chosen it-system it is marked as self-owned. The it-system uuid should be set in the variable `SELF_OWNED_IT_SYSTEM_CHECK`
## Usage

Adjust the `AMQP__URL` variable to OS2mo's running message-broker, either;
* directly in `docker-compose.yml` or
* by creating a `docker-compose.override.yaml` file.

Now start the container using `docker-compose`:
```
docker-compose up -d
```

You should see the following:
```
[info     ] Starting metrics server        port=800
[info     ] Register called                function=organisation_gatekeeper_callback routing_key=org_unit.org_unit.*
[info     ] Starting AMQP system
[info     ] Establishing AMQP connection   host=msg_broker path=/ port=5672 scheme=amqp user=guest
[info     ] Creating AMQP channel
[info     ] Attaching AMQP exchange to channel exchange=os2mo
[info     ] Declaring unique message queue function=organisation_gatekeeper_callback queue_name=os2mo-amqp-trigger-organisation-gatekeeper_organisation_gatekeeper_callback
[info     ] Starting message listener      function=organisation_gatekeeper_callback
[info     ] Binding routing keys           function=organisation_gatekeeper_callback
[info     ] Binding routing-key            function=organisation_gatekeeper_callback routing_key=org_unit.org_unit.*
```
After which each message will add:
```
[debug    ] Received message               function=organisation_gatekeeper_callback routing_key=org_unit.org_unit.edit
[info     ] Message received               object_type=org_unit payload=... request_type=edit service_type=org_unit
```
And at which point metrics should be available at `localhost:8000`, and line management information will be updated.

## Development

### Prerequisites

- [Poetry](https://github.com/python-poetry/poetry)

### Getting Started

1. Clone the repository:
```
git clone git@git.magenta.dk:rammearkitektur/os2mo-triggers/os2mo-amqp-trigger-organisation-gatekeeper.git
```

2. Install all dependencies:
```
poetry install
```

3. Set up pre-commit:
```
poetry run pre-commit install
```

### Running the tests

You use `poetry` and `pytest` to run the tests:

`poetry run pytest`

You can also run specific files

`poetry run pytest tests/<test_folder>/<test_file.py>`

and even use filtering with `-k`

`poetry run pytest -k "Manager"`

You can use the flags `-vx` where `v` prints the test & `x` makes the test stop if any tests fails (Verbose, X-fail)

#### Running the integration tests

To run the integration tests, an AMQP instance must be available.

If an instance is already available, it can be used by configuring the `AMQP__URL`
environmental variable. Alternatively a RabbitMQ can be started in docker, using:
```
docker run -d -p 5672:5672 -p 15672:15672 rabbitmq:3-management
```

## Versioning

This project uses [Semantic Versioning](https://semver.org/) with the following strategy:
- MAJOR: Incompatible changes to existing data models
- MINOR: Backwards compatible updates to existing data models OR new models added
- PATCH: Backwards compatible bug fixes

## Authors

Magenta ApS <https://magenta.dk>

## License

This project uses: [MPL-2.0](MPL-2.0.txt)

This project uses [REUSE](https://reuse.software) for licensing.
All licenses can be found in the [LICENSES folder](LICENSES/) of the project.
