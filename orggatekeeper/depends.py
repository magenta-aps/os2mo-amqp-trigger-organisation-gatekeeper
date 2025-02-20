# SPDX-FileCopyrightText: Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0
"""Helper module for defining dependencies that are extracted from Context"""
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastramqpi.depends import from_user_context

from .config import Settings as _Settings

Settings = Annotated[_Settings, Depends(from_user_context("settings"))]
OrgUuid = Annotated[UUID, Depends(from_user_context("org_uuid"))]
