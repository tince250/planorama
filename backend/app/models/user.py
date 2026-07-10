from pydantic import BaseModel, Field

USERNAME_PATTERN = r"^[A-Za-z0-9_.-]{3,32}$"


class RegisterRequest(BaseModel):
    username: str = Field(pattern=USERNAME_PATTERN)
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    username: str


class PreferencesOut(BaseModel):
    categories: list[str]
    budget_min: float | None = None
    budget_max: float | None = None
    home_lat: float | None = None
    home_lon: float | None = None
