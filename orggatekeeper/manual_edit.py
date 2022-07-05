# SPDX-FileCopyrightText: 2019-2020 Magenta ApS
# SPDX-License-Identifier: MPL-2.0
import requests

REALM = "mo"
BASEURL = "http://os2mo.example.com"

# Get token from Keycloak

token_url = BASEURL + f"/auth/realms/{REALM}/protocol/openid-connect/token"
payload = {
    "grant_type": "client_credentials",
    "client_id": "integration_orggatekeeper",
    "client_secret": "3CT4G2PRJZ6R4YZT5BXR2D544F6XCHTVNLHVKCTA",
}

r = requests.post(token_url, data=payload)
print(r.status_code, r.url)
token = r.json()["access_token"]

# Call MOs backend with the Keycloak token

headers = {"Authorization": f"bearer {token}"}

# r = requests.get("http://os2mo.example.com/service/o/", headers=headers)
# print(r.status_code, r.url)

payload = {
    "type": "org_unit",
    "data": {
        "uuid": "4e805460-01e1-5d89-a266-d139bca98221",
        "org_unit_hierarchy": {
            "uuid": "f805eb80-fdfe-8f24-9367-68ea955b9b9b"
        },
        "validity": {
            "from": "2022-07-01",
            "to": None
        },
    }
}

r = requests.post(BASEURL + "/service/details/edit", headers=headers, json=payload)
print(r.status_code, r.url)
print(r.json())
