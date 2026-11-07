"""HTML pages (Jinja2).

Each page is a template that extends base.html. The pages themselves are public, but the
*data* comes from the JSON API through JavaScript (static/js/app.js), which sends the
login token. So there is exactly one place where posts, permissions and validation live:
the API routers. The pages contain no business logic.
"""
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..config import settings

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")
templates.env.globals["app_name"] = settings.app_name


def _page(request: Request, template: str, **context) -> HTMLResponse:
    return templates.TemplateResponse(request, template, context)


@router.get("/")
def feed(request: Request):
    return _page(request, "feed.html")


@router.get("/login")
def login_page(request: Request):
    return _page(request, "login.html")


@router.get("/register")
def register_page(request: Request):
    return _page(request, "register.html")


@router.get("/forgot-password")
def forgot_password_page(request: Request):
    return _page(request, "forgot_password.html")


@router.get("/reset-password")
def reset_password_page(request: Request):
    return _page(request, "reset_password.html")


@router.get("/account")
def account_page(request: Request):
    return _page(request, "account.html")


@router.get("/post/{post_id}")
def post_page(request: Request, post_id: int):
    return _page(request, "post.html", post_id=post_id)


@router.get("/u/{username}")
def profile_page(request: Request, username: str):
    # `username` is auto-escaped by Jinja2 when printed, and JS reads it from a data attribute.
    return _page(request, "profile.html", username=username)
