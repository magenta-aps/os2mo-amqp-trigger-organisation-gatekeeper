import asyncio
from operator import itemgetter
from typing import List, Dict

import requests
from gql import gql

from raclients.graph.client import PersistentGraphQLClient
from config import get_settings


settings = get_settings()

gql_client = PersistentGraphQLClient(
    url=settings.mo_url + "/graphql",
    client_id=settings.client_id,
    client_secret=settings.client_secret.get_secret_value(),
    auth_server=settings.auth_server,
    auth_realm=settings.auth_realm,
    execute_timeout=settings.graphql_timeout,
    httpx_client_kwargs={"timeout": settings.graphql_timeout},
)


async def gql_query():
    query = gql("query OrgUnitUUIDQuery { org_units { uuid } }")
    r = await gql_client.execute(query)
    # print(r)
    # r = {'org_units': [{'uuid': 'fea1c6ba-1ed8-4800-9200-000001290002'}, {'uuid': 'fff4caba-1ed8-4800-a800-0000012a0002'}]}
    return list(map(itemgetter("uuid"), r["org_units"]))


async def main():
    org_unit_uuids = (await asyncio.gather(gql_query()))[0]
    failed_units = []
    counter = 1
    for uuid in org_unit_uuids:
        print(uuid, counter)
        r = requests.post(f"http://localhost:8000/trigger/{uuid}")
        if r.status_code != 200:
            print(f"failed: {uuid}", r.status_code, r.text)
            failed_units.append({"uuid": uuid, "status": r.status_code, "text": r.text})
        counter += 1
    for unit in failed_units:
        print(unit)

if __name__ == "__main__":
    asyncio.run(main())
