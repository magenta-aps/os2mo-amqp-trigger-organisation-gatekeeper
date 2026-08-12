# SPDX-FileCopyrightText: Magenta ApS <https://magenta.dk>
# SPDX-License-Identifier: MPL-2.0

import pytest

# TODO: these will be removed in a following commit, they are needed for the pipeline
#   to not fail, because it is not allowed to have less than 2 integration tests


@pytest.mark.integration_test
async def test_dummy_1() -> None:
    assert True


@pytest.mark.integration_test
async def test_dummy_2() -> None:
    assert True
