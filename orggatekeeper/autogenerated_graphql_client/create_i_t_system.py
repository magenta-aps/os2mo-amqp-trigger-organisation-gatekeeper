from uuid import UUID

from .base_model import BaseModel


class CreateITSystem(BaseModel):
    itsystem_create: "CreateITSystemItsystemCreate"


class CreateITSystemItsystemCreate(BaseModel):
    uuid: UUID


CreateITSystem.update_forward_refs()
CreateITSystemItsystemCreate.update_forward_refs()
