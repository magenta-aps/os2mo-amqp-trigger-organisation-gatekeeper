from .async_base_client import AsyncBaseClient
from .dummy_query import DummyQuery
from .dummy_query import DummyQueryOrg


def gql(q: str) -> str:
    return q


class GraphQLClient(AsyncBaseClient):
    async def dummy_query(self) -> DummyQueryOrg:
        query = gql("""
            query DummyQuery {
              org {
                uuid
              }
            }
            """)
        variables: dict[str, object] = {}
        response = await self.execute(query=query, variables=variables)
        data = self.get_data(response)
        return DummyQuery.parse_obj(data).org
