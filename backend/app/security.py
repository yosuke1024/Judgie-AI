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
    SSRF protection: validates that a URL resolves to a permitted domain and not a private/internal IP.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        # Allow only specified domains
        allowed_domains = {
            "github.com",
            "raw.githubusercontent.com",
            "gist.githubusercontent.com",
            "githubusercontent.com",
        }

        if hostname not in allowed_domains:
            return False

        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return False
        except ValueError:
            try:
                addr_info = socket.getaddrinfo(hostname, None)
                for addr in addr_info:
                    ip_str = addr[4][0]
                    ip = ipaddress.ip_address(ip_str)
                    if ip.is_private or ip.is_loopback or ip.is_link_local:
                        return False
            except socket.gaierror:
                return False
        return True
    except Exception:
        return False
