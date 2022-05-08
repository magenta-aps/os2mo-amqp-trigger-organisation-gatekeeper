# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
# pylint: disable=redefined-outer-name
"""This module contains pytest specific code, fixtures and helpers."""
import pytest
import structlog
from structlog.testing import LogCapture


@pytest.fixture
def log_output() -> LogCapture:
    """Pytest fixture to construct an LogCapture."""
    return LogCapture()


@pytest.fixture(autouse=True)
def fixture_configure_structlog(log_output: LogCapture) -> None:
    """Pytest autofixture to capture all logs."""
    structlog.configure(processors=[log_output])
