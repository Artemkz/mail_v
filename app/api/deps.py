from fastapi import Request

from app.services.auth_service import get_current_username as _get_current_username


async def get_current_username(request: Request) -> str:
  return _get_current_username(request)
