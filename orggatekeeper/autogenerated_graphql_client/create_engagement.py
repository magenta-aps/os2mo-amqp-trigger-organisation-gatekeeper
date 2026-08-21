from uuid import UUID

from .base_model import BaseModel


class CreateEngagement(BaseModel):
    engagement_create: "CreateEngagementEngagementCreate"


class CreateEngagementEngagementCreate(BaseModel):
    uuid: UUID


CreateEngagement.update_forward_refs()
CreateEngagementEngagementCreate.update_forward_refs()
