from typing import List, Optional
from uuid import UUID

from .base_model import BaseModel


class GetOrgUnitHierarchy(BaseModel):
    org_units: "GetOrgUnitHierarchyOrgUnits"


class GetOrgUnitHierarchyOrgUnits(BaseModel):
    objects: List["GetOrgUnitHierarchyOrgUnitsObjects"]


class GetOrgUnitHierarchyOrgUnitsObjects(BaseModel):
    validities: List["GetOrgUnitHierarchyOrgUnitsObjectsValidities"]


class GetOrgUnitHierarchyOrgUnitsObjectsValidities(BaseModel):
    unit_hierarchy_response: Optional[
        "GetOrgUnitHierarchyOrgUnitsObjectsValiditiesUnitHierarchyResponse"
    ]


class GetOrgUnitHierarchyOrgUnitsObjectsValiditiesUnitHierarchyResponse(BaseModel):
    validities: List[
        "GetOrgUnitHierarchyOrgUnitsObjectsValiditiesUnitHierarchyResponseValidities"
    ]


class GetOrgUnitHierarchyOrgUnitsObjectsValiditiesUnitHierarchyResponseValidities(
    BaseModel
):
    uuid: UUID


GetOrgUnitHierarchy.update_forward_refs()
GetOrgUnitHierarchyOrgUnits.update_forward_refs()
GetOrgUnitHierarchyOrgUnitsObjects.update_forward_refs()
GetOrgUnitHierarchyOrgUnitsObjectsValidities.update_forward_refs()
GetOrgUnitHierarchyOrgUnitsObjectsValiditiesUnitHierarchyResponse.update_forward_refs()
GetOrgUnitHierarchyOrgUnitsObjectsValiditiesUnitHierarchyResponseValidities.update_forward_refs()
