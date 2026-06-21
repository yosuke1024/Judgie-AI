"""
Security utilities: password hashing and URL validation.
Adapted from core/security.py (100% reuse, no Streamlit dependency).
"""

import ipaddress
import socket
from urllib.parse import urlparse

import bcrypt


def hash_passcode(plain: str) -> str:
    """Hash a passcode using bcrypt."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_passcode(plain: str, hashed: str) -> bool:
    """Verify a plaintext passcode against its bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def is_safe_url(url: str) -> bool:
    """
    SSRF protection: validates that a URL does not resolve to a private/internal IP.
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return False
        resolved_ip = socket.gethostbyname(hostname)
        ip_obj = ipaddress.ip_address(resolved_ip)
        return not ip_obj.is_private and not ip_obj.is_loopback and not ip_obj.is_reserved
    except Exception:
        return False
