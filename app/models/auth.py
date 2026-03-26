from typing import Literal

from pydantic import BaseModel, EmailStr, Field, constr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: constr(min_length=8)
    name: str = Field(min_length=1, max_length=255)
    position: str | None = Field(default=None, max_length=100)
    role: Literal["newcomer", "experienced"]
    invite_code: constr(
        min_length=8,
        max_length=8,
        pattern=r"^[A-Za-z0-9]{8}$",
    )


class RegisterCompanyRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: constr(min_length=8)
    name: str = Field(min_length=1, max_length=255)
    position: str | None = Field(default=None, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)
