import asyncio
from uuid import UUID

from raclients.graph.client import PersistentGraphQLClient
from .config import get_settings
from .mo import fetch_org_unit

OU_UUID = "5ac5fdba-1ed8-4800-b000-0000012a0002"

settings = get_settings()

gql_client = PersistentGraphQLClient(
    url=settings.mo_url + "/graphql",
    client_id=settings.client_id,
    client_secret=settings.client_secret.get_secret_value(),
    auth_server=settings.auth_server,
    auth_realm=settings.auth_realm,
    execute_timeout=settings.graphql_timeout,
    sync=True,
    httpx_client_kwargs={"timeout": settings.graphql_timeout},
)


async def query():
    ou = await fetch_org_unit(UUID(OU_UUID))
    print(ou.org_unit_hierarchy)


async def main():
    await asyncio.gather(query())


if __name__ == "__main__":
    asyncio.run(main())
