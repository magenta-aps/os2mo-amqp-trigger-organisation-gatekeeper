from uuid import UUID

from .base_model import BaseModel


class CreateAssociation(BaseModel):
    association_create: "CreateAssociationAssociationCreate"


class CreateAssociationAssociationCreate(BaseModel):
    uuid: UUID


CreateAssociation.update_forward_refs()
CreateAssociationAssociationCreate.update_forward_refs()
