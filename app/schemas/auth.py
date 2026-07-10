"""Auth-related schemas."""
import uuid

from pydantic import BaseModel, ConfigDict

from app.enums import Role, UserStatus


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str | None = None
    role: Role
    shop_id: uuid.UUID | None
    status: UserStatus
