from uuid import UUID

from .base_model import BaseModel


class CreateFacet(BaseModel):
    facet_create: "CreateFacetFacetCreate"


class CreateFacetFacetCreate(BaseModel):
    uuid: UUID


CreateFacet.update_forward_refs()
CreateFacetFacetCreate.update_forward_refs()
