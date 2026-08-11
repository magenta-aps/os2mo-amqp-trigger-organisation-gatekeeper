## Starting the stack
- Integration tests require "the stack" to be running
- Ensure the os2mo stack is running:
  - If the os2mo repository is not available in your environment, you can clone it from: https://github.com/OS2mo/os2mo
  - The os2mo README should explain how to start the stack
- Ensure the local stack is running:
  - Start it via: `docker compose up -d --build`

## Running tests
- There are *unit tests* and *integration tests*

- Unit tests are located in `tests/`, except for `test/integration/`
- Unit tests can be run without starting the stack
- Running unit tests alone does not prove your code is correct, you must also
  run integration tests.

- Integration tests are located in `tests/integration/`
- Integration tests require **starting the stack** if it isn't running
- Run integration tests via: `docker compose run --rm orggatekeeper pytest <test-path>`

## Rules
- Always ask for confirmation before editing the local git hooks, git config or git excluded files
- Always prefer running integration tests over trying to infer if your code is correct
- If something is preventing you from running tests, report it to the user, rather than skipping the tests
