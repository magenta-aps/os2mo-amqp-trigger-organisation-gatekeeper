from .async_base_client import AsyncBaseClient
from .create_class import CreateClass, CreateClassClassCreate
from .create_employee import CreateEmployee, CreateEmployeeEmployeeCreate
from .create_engagement import CreateEngagement, CreateEngagementEngagementCreate
from .create_facet import CreateFacet, CreateFacetFacetCreate
from .create_org_unit import CreateOrgUnit, CreateOrgUnitOrgUnitCreate
from .get_class_by_user_key import GetClassByUserKey, GetClassByUserKeyClasses
from .get_org_unit_hierarchy import GetOrgUnitHierarchy, GetOrgUnitHierarchyOrgUnits
from .input_types import (
    ClassCreateInput,
    ClassFilter,
    EmployeeCreateInput,
    EngagementCreateInput,
    FacetCreateInput,
    OrganisationUnitCreateInput,
    OrganisationUnitFilter,
)


def gql(q: str) -> str:
    return q


class GraphQLClient(AsyncBaseClient):
    async def get_org_unit_hierarchy(
        self, filter: OrganisationUnitFilter
    ) -> GetOrgUnitHierarchyOrgUnits:
        query = gql("""
            query GetOrgUnitHierarchy($filter: OrganisationUnitFilter!) {
              org_units(filter: $filter) {
                objects {
                  validities {
                    unit_hierarchy_response {
                      validities {
                        uuid
                      }
                    }
                  }
                }
              }
            }
            """)
        variables: dict[str, object] = {"filter": filter}
        response = await self.execute(query=query, variables=variables)
        data = self.get_data(response)
        return GetOrgUnitHierarchy.parse_obj(data).org_units

    async def get_class_by_user_key(
        self, filter: ClassFilter
    ) -> GetClassByUserKeyClasses:
        query = gql("""
            query GetClassByUserKey($filter: ClassFilter!) {
              classes(filter: $filter) {
                objects {
                  uuid
                  current {
                    user_key
                  }
                }
              }
            }
            """)
        variables: dict[str, object] = {"filter": filter}
        response = await self.execute(query=query, variables=variables)
        data = self.get_data(response)
        return GetClassByUserKey.parse_obj(data).classes

    async def create_org_unit(
        self, input: OrganisationUnitCreateInput
    ) -> CreateOrgUnitOrgUnitCreate:
        query = gql("""
            mutation CreateOrgUnit($input: OrganisationUnitCreateInput!) {
              org_unit_create(input: $input) {
                uuid
              }
            }
            """)
        variables: dict[str, object] = {"input": input}
        response = await self.execute(query=query, variables=variables)
        data = self.get_data(response)
        return CreateOrgUnit.parse_obj(data).org_unit_create

    async def create_facet(self, input: FacetCreateInput) -> CreateFacetFacetCreate:
        query = gql("""
            mutation CreateFacet($input: FacetCreateInput!) {
              facet_create(input: $input) {
                uuid
              }
            }
            """)
        variables: dict[str, object] = {"input": input}
        response = await self.execute(query=query, variables=variables)
        data = self.get_data(response)
        return CreateFacet.parse_obj(data).facet_create

    async def create_class(self, input: ClassCreateInput) -> CreateClassClassCreate:
        query = gql("""
            mutation CreateClass($input: ClassCreateInput!) {
              class_create(input: $input) {
                uuid
              }
            }
            """)
        variables: dict[str, object] = {"input": input}
        response = await self.execute(query=query, variables=variables)
        data = self.get_data(response)
        return CreateClass.parse_obj(data).class_create

    async def create_employee(
        self, input: EmployeeCreateInput
    ) -> CreateEmployeeEmployeeCreate:
        query = gql("""
            mutation CreateEmployee($input: EmployeeCreateInput!) {
              employee_create(input: $input) {
                uuid
              }
            }
            """)
        variables: dict[str, object] = {"input": input}
        response = await self.execute(query=query, variables=variables)
        data = self.get_data(response)
        return CreateEmployee.parse_obj(data).employee_create

    async def create_engagement(
        self, input: EngagementCreateInput
    ) -> CreateEngagementEngagementCreate:
        query = gql("""
            mutation CreateEngagement($input: EngagementCreateInput!) {
              engagement_create(input: $input) {
                uuid
              }
            }
            """)
        variables: dict[str, object] = {"input": input}
        response = await self.execute(query=query, variables=variables)
        data = self.get_data(response)
        return CreateEngagement.parse_obj(data).engagement_create
