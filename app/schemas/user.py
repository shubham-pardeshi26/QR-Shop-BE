"""User (staff/admin) provisioning schemas."""
from pydantic import BaseModel, EmailStr, Field

from app.enums import UserStatus


class StaffCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=120)


class StaffUpdate(BaseModel):
    status: UserStatus | None = None
    name: str | None = Field(default=None, max_length=120)
