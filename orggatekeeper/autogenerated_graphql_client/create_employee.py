from uuid import UUID

from .base_model import BaseModel


class CreateEmployee(BaseModel):
    employee_create: "CreateEmployeeEmployeeCreate"


class CreateEmployeeEmployeeCreate(BaseModel):
    uuid: UUID


CreateEmployee.update_forward_refs()
CreateEmployeeEmployeeCreate.update_forward_refs()
