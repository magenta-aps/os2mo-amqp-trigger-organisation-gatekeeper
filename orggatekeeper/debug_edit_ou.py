import asyncio
from uuid import UUID

from .config import get_settings
from .main import construct_clients
from .main import update_line_management
from .mo import fetch_org_uuid

LINJEORG_UUID = "f805eb80-fdfe-8f24-9367-68ea955b9b9b"
OU_UUID = "1a477478-41b4-4806-ac3a-e220760a0c89"

settings = get_settings(
    client_secret="HVJVD4WPIQ6EXWRC65CBVJPTTLFJEJQ4THBZZQBS",
    mo_url="http://os2mo.example.com",
    client_id="integration_orggatekeeper",
    auth_server="http://os2mo.example.com/auth"
)
gql_client, model_client = construct_clients(settings)


async def query():
    """query called"""
    org_uuid = await fetch_org_uuid(gql_client)
    result = await update_line_management(gql_client, model_client, settings, org_uuid, UUID(OU_UUID))
    print(result)


async def main():
    await asyncio.gather(query())
    # r = await asyncio.gather(fetch_org_uuid(gql_client))
    # print(r[0])


if __name__ == "__main__":
    asyncio.run(main())
