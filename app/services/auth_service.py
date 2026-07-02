from datetime import UTC, datetime, timedelta
import secrets

import jwt
from fastapi import HTTPException, Request, status

from app.config import settings


def authenticate_user(username: str, password: str) -> bool:
  user_ok = secrets.compare_digest(username, settings.app_username)
  pass_ok = secrets.compare_digest(password, settings.app_password)
  return user_ok and pass_ok


def create_access_token(username: str) -> str:
  expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
  payload = {"sub": username, "exp": expire}
  return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> str:
  try:
    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    username = payload.get("sub")
    if not username:
      raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительный токен")
    return username
  except jwt.PyJWTError as exc:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительный токен") from exc


def get_token_from_request(request: Request) -> str | None:
  cookie_token = request.cookies.get(settings.cookie_name)
  if cookie_token:
    return cookie_token

  auth_header = request.headers.get("Authorization")
  if auth_header and auth_header.startswith("Bearer "):
    return auth_header.removeprefix("Bearer ").strip()
  return None


def get_current_username(request: Request) -> str:
  token = get_token_from_request(request)
  if not token:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется авторизация")
  return decode_access_token(token)
