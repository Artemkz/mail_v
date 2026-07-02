from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, RedirectResponse

from app.services.auth_service import decode_access_token, get_token_from_request

router = APIRouter(tags=["web"])

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def _is_authenticated(request: Request) -> bool:
  token = get_token_from_request(request)
  if not token:
    return False
  try:
    decode_access_token(token)
    return True
  except Exception:
    return False


@router.get("/login")
async def login_page() -> FileResponse:
  return FileResponse(STATIC_DIR / "login.html")


@router.get("/")
async def index(request: Request):
  if not _is_authenticated(request):
    return RedirectResponse(url="login", status_code=302)
  return FileResponse(STATIC_DIR / "index.html")
