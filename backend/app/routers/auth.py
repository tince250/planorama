from fastapi import APIRouter, HTTPException

from app.auth.passwords import hash_password, verify_password
from app.models.user import AuthResponse, LoginRequest, RegisterRequest
from app.queries.users import create_user, get_credentials, user_exists

router = APIRouter(prefix="/auth")


@router.post("/register", response_model=AuthResponse)
def register(request: RegisterRequest):
    if user_exists(request.username):
        raise HTTPException(status_code=409, detail="Username already taken")
    password_hash, salt = hash_password(request.password)
    create_user(request.username, password_hash, salt)
    return AuthResponse(username=request.username)


@router.post("/login", response_model=AuthResponse)
def login(request: LoginRequest):
    credentials = get_credentials(request.username)
    if credentials is None or not verify_password(request.password, *credentials):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return AuthResponse(username=request.username)
