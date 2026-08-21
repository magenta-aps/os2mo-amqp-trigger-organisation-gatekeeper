from uuid import UUID

from .base_model import BaseModel


class CreateITUser(BaseModel):
    ituser_create: "CreateITUserItuserCreate"


class CreateITUserItuserCreate(BaseModel):
    uuid: UUID


CreateITUser.update_forward_refs()
CreateITUserItuserCreate.update_forward_refs()
