from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import Field

from .base_model import BaseModel


class GetOrgUnitHierarchyAndParent(BaseModel):
    org_units: "GetOrgUnitHierarchyAndParentOrgUnits"


class GetOrgUnitHierarchyAndParentOrgUnits(BaseModel):
    objects: List["GetOrgUnitHierarchyAndParentOrgUnitsObjects"]


class GetOrgUnitHierarchyAndParentOrgUnitsObjects(BaseModel):
    validities: List["GetOrgUnitHierarchyAndParentOrgUnitsObjectsValidities"]


class GetOrgUnitHierarchyAndParentOrgUnitsObjectsValidities(BaseModel):
    unit_hierarchy_response: Optional[
        "GetOrgUnitHierarchyAndParentOrgUnitsObjectsValiditiesUnitHierarchyResponse"
    ]
    parent_response: Optional[
        "GetOrgUnitHierarchyAndParentOrgUnitsObjectsValiditiesParentResponse"
    ]
    validity: "GetOrgUnitHierarchyAndParentOrgUnitsObjectsValiditiesValidity"


class GetOrgUnitHierarchyAndParentOrgUnitsObjectsValiditiesUnitHierarchyResponse(
    BaseModel
):
    uuid: UUID


class GetOrgUnitHierarchyAndParentOrgUnitsObjectsValiditiesParentResponse(BaseModel):
    uuid: UUID


class GetOrgUnitHierarchyAndParentOrgUnitsObjectsValiditiesValidity(BaseModel):
    from_: datetime = Field(alias="from")
    to: Optional[datetime]


GetOrgUnitHierarchyAndParent.update_forward_refs()
GetOrgUnitHierarchyAndParentOrgUnits.update_forward_refs()
GetOrgUnitHierarchyAndParentOrgUnitsObjects.update_forward_refs()
GetOrgUnitHierarchyAndParentOrgUnitsObjectsValidities.update_forward_refs()
GetOrgUnitHierarchyAndParentOrgUnitsObjectsValiditiesUnitHierarchyResponse.update_forward_refs()
GetOrgUnitHierarchyAndParentOrgUnitsObjectsValiditiesParentResponse.update_forward_refs()
GetOrgUnitHierarchyAndParentOrgUnitsObjectsValiditiesValidity.update_forward_refs()
