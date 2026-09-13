from fastapi import APIRouter, Header, HTTPException, status

from app.schemas.auth import LoginRequest, LoginResponse, UserProfile
from app.security.auth import authenticate, authenticated_user, create_session_token, user_profile

router = APIRouter()



@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest) -> LoginResponse:
    if not authenticate(request.user_id, request.pin):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid demo credentials")
    token = create_session_token(request.user_id)
    profile = user_profile(request.user_id)
    return LoginResponse(access_token=token, **profile)


@router.get("/me", response_model=UserProfile)
def me(authorization: str | None = Header(default=None)) -> UserProfile:
    user_id = authenticated_user(authorization)
    return UserProfile(**user_profile(user_id))

