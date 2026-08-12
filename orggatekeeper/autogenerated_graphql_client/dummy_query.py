from uuid import UUID

from .base_model import BaseModel


class DummyQuery(BaseModel):
    org: "DummyQueryOrg"


class DummyQueryOrg(BaseModel):
    uuid: UUID


DummyQuery.update_forward_refs()
DummyQueryOrg.update_forward_refs()
