from uuid import UUID

from .base_model import BaseModel


class CreateOrgUnit(BaseModel):
    org_unit_create: "CreateOrgUnitOrgUnitCreate"


class CreateOrgUnitOrgUnitCreate(BaseModel):
    uuid: UUID


CreateOrgUnit.update_forward_refs()
CreateOrgUnitOrgUnitCreate.update_forward_refs()
