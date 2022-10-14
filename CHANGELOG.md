<!--
SPDX-FileCopyrightText: 2021 Magenta ApS <https://magenta.dk>
SPDX-License-Identifier: MPL-2.0
-->

CHANGELOG
=========

2.4.0 - 2022-10-14
------------------

[#46148] Add a check if org_units below a unit is line-management to get the top org_units to be shown as line-management.

2.3.0 - 2022-10-14
------------------

[#56148] Configure top level line-management units and hidden units with uuids instead of user_keys, as user_keys are not guarantied to be unique. Always set unit to line_management if it is found in LINE_MANAGEMENT_TOP_LEVEL_USER_UUIDS

2.2.2 - 2022-10-06
------------------

[#51982] Update dependencies

2.2.1 - 2022-10-05
------------------

[#52332] Sleep on errors to avoid overloading MO

2.2.0 - 2022-09-26
------------------

[#50861] Switch to use new version of graphql api where org_unit parents are no longer lists.

2.1.0 - 2022-09-08
------------------

[#51474] Adds a check to the line management calculation which checks if the organisation unit is below the main line management organisation. Controlled by a user_key set in settings.

2.0.0 - 2022-08-25
------------------

[#51926] Bump RAMQP version; reduce prefetch_count from (default) 10 to 1

1.1.2 - 2022-08-15
------------------

[#51474] Fix deploy with configupdater to update orggatekeeper and not orgviewer

1.1.1 - 2022-08-12
------------------

[#51474] Adds automatic relases with config updater

1.1.0 - 2022-08-11
------------------

[#51474] Adds support for self-owned organisations and organisations without hierarchies.

1.0.4 - 2022-07-04
------------------

[#46148] Handle linjeorg markup of root org units

1.0.3 - 2022-07-01
------------------

[#46148] Fixed linjeorg markup bug

1.0.2 - 2022-06-28
------------------

[#46148] Set execution timeout for asyncio.wait_for

1.0.1 - 2022-06-28
------------------

[#46148] Increase GraphQL timeout

1.0.0 - 2022-06-27
------------------

[#46148] Use current date as from_date validity when modifying org units

0.3.0 - 2022-06-22
------------------

[#46148] Added Kubernetes health endpoints

0.2.0 - 2022-06-10
------------------

[#46148] Added FastAPI handles

