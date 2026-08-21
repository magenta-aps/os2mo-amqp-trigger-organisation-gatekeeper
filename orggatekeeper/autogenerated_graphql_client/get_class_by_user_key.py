from typing import List, Optional
from uuid import UUID

from .base_model import BaseModel


class GetClassByUserKey(BaseModel):
    classes: "GetClassByUserKeyClasses"


class GetClassByUserKeyClasses(BaseModel):
    objects: List["GetClassByUserKeyClassesObjects"]


class GetClassByUserKeyClassesObjects(BaseModel):
    uuid: UUID
    current: Optional["GetClassByUserKeyClassesObjectsCurrent"]


class GetClassByUserKeyClassesObjectsCurrent(BaseModel):
    user_key: str


GetClassByUserKey.update_forward_refs()
GetClassByUserKeyClasses.update_forward_refs()
GetClassByUserKeyClassesObjects.update_forward_refs()
GetClassByUserKeyClassesObjectsCurrent.update_forward_refs()
