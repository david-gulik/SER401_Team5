"""PKCE (Proof Key for Code Exchange) utilities for ASU's serviceauth OAuth flow."""

import base64
import hashlib
import secrets
import string


def generate_code_verifier(length: int = 64) -> str:
    """Generate a random code verifier (RFC 7636, 43-128 chars)."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def compute_code_challenge(verifier: str) -> str:
    """Compute the S256 code challenge from a verifier."""
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
