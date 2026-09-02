from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import Field

from .base_model import BaseModel


class GetOrgUnitDetails(BaseModel):
    org_units: "GetOrgUnitDetailsOrgUnits"


class GetOrgUnitDetailsOrgUnits(BaseModel):
    objects: List["GetOrgUnitDetailsOrgUnitsObjects"]


class GetOrgUnitDetailsOrgUnitsObjects(BaseModel):
    validities: List["GetOrgUnitDetailsOrgUnitsObjectsValidities"]


class GetOrgUnitDetailsOrgUnitsObjectsValidities(BaseModel):
    name: str
    user_key: str
    unit_hierarchy_response: Optional[
        "GetOrgUnitDetailsOrgUnitsObjectsValiditiesUnitHierarchyResponse"
    ]
    unit_type_response: Optional[
        "GetOrgUnitDetailsOrgUnitsObjectsValiditiesUnitTypeResponse"
    ]
    unit_level_response: Optional[
        "GetOrgUnitDetailsOrgUnitsObjectsValiditiesUnitLevelResponse"
    ]
    parent_response: Optional[
        "GetOrgUnitDetailsOrgUnitsObjectsValiditiesParentResponse"
    ]
    validity: "GetOrgUnitDetailsOrgUnitsObjectsValiditiesValidity"


class GetOrgUnitDetailsOrgUnitsObjectsValiditiesUnitHierarchyResponse(BaseModel):
    uuid: UUID


class GetOrgUnitDetailsOrgUnitsObjectsValiditiesUnitTypeResponse(BaseModel):
    uuid: UUID


class GetOrgUnitDetailsOrgUnitsObjectsValiditiesUnitLevelResponse(BaseModel):
    uuid: UUID


class GetOrgUnitDetailsOrgUnitsObjectsValiditiesParentResponse(BaseModel):
    uuid: UUID


class GetOrgUnitDetailsOrgUnitsObjectsValiditiesValidity(BaseModel):
    from_: datetime = Field(alias="from")
    to: Optional[datetime]


GetOrgUnitDetails.update_forward_refs()
GetOrgUnitDetailsOrgUnits.update_forward_refs()
GetOrgUnitDetailsOrgUnitsObjects.update_forward_refs()
GetOrgUnitDetailsOrgUnitsObjectsValidities.update_forward_refs()
GetOrgUnitDetailsOrgUnitsObjectsValiditiesUnitHierarchyResponse.update_forward_refs()
GetOrgUnitDetailsOrgUnitsObjectsValiditiesUnitTypeResponse.update_forward_refs()
GetOrgUnitDetailsOrgUnitsObjectsValiditiesUnitLevelResponse.update_forward_refs()
GetOrgUnitDetailsOrgUnitsObjectsValiditiesParentResponse.update_forward_refs()
GetOrgUnitDetailsOrgUnitsObjectsValiditiesValidity.update_forward_refs()
