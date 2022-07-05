from raclients.modelclient.mo import ModelClient
from ramodels.mo import OrganisationUnit

from .config import get_settings


settings = get_settings(client_secret="hurra")

model_client = ModelClient(
    base_url=settings.mo_url,
    client_id=settings.client_id,
    client_secret=settings.client_secret.get_secret_value(),
    auth_server=settings.auth_server,
    auth_realm=settings.auth_realm,
)

ou = OrganisationUnit()
