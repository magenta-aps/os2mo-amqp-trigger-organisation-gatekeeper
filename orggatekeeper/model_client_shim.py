# SPDX-FileCopyrightText: Magenta ApS <https://magenta.dk>
# SPDX-License-Identifier: MPL-2.0

"""Shims for adapting calls to ModelClient to call the graphql API instead."""

from typing import cast

from fastramqpi.raclients.modelclient.mo import ModelClient
from ramodels.mo import OrganisationUnit


async def edit(model_client: ModelClient, edit_obj: OrganisationUnit) -> list[str]:
    response = await model_client.edit([edit_obj])
    return cast(list[str], response)
