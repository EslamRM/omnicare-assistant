from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=100)
    pin: str = Field(..., min_length=4, max_length=32)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    display_name: str
    policies: list[str]
    token_expires_in_seconds: int


class UserProfile(BaseModel):
    user_id: str
    display_name: str
    policies: list[str]
    token_expires_in_seconds: int
