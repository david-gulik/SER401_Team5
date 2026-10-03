from __future__ import annotations

from argparse import Namespace

from GAVEL.app_context import AppContext
from GAVEL.infra.asu_auth.cookie_store import CookieStore


def handle_asu_login_forget(ctx: AppContext, args: Namespace) -> int:
    """Delete the login cookies kept between runs; the next download signs in again."""
    browser = ctx.services.asu_browser
    removed = browser.forget() if browser is not None else CookieStore().clear()
    if removed:
        print("Saved ASU login removed. The next download will ask you to sign in.")
    else:
        print("No saved ASU login to remove.")
    return 0
