from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.config import settings
from app.api.deps import get_current_username
from app.schemas.auth import LoginRequest, UserResponse
from app.services.auth_service import authenticate_user, create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=UserResponse)
async def login(payload: LoginRequest, response: Response) -> UserResponse:
  if not authenticate_user(payload.username, payload.password):
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Неверный логин или пароль",
    )

  token = create_access_token(payload.username)
  response.set_cookie(
    key=settings.cookie_name,
    value=token,
    httponly=True,
    max_age=settings.access_token_expire_minutes * 60,
    samesite="lax",
    secure=settings.cookie_secure,
    path=settings.cookie_path,
  )
  return UserResponse(username=payload.username)


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
  response.delete_cookie(
    key=settings.cookie_name,
    path=settings.cookie_path,
  )
  return {"status": "ok"}


@router.get("/me", response_model=UserResponse)
async def me(username: str = Depends(get_current_username)) -> UserResponse:
  return UserResponse(username=username)
