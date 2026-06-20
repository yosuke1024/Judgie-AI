import ipaddress
import socket
from urllib.parse import urlparse

import bcrypt


def hash_passcode(passcode: str) -> str:
    """Hash a plain passcode"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(passcode.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_passcode(plain_passcode: str, hashed_passcode: str) -> bool:
    """Verify that the plain passcode matches the hashed passcode"""
    try:
        return bcrypt.checkpw(plain_passcode.encode("utf-8"), hashed_passcode.encode("utf-8"))
    except Exception:
        return False


def is_safe_url(url: str) -> bool:
    """SSRF mitigation: Allow only authorized domains (e.g. GitHub) and block requests to local or private IPs."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        # Check the host against a whitelist of allowed domains so that static analysis tools (like CodeQL) recognize this as a sanitizer
        # In practice, custom template sharing is limited to GitHub (including raw and gist domains)
        allowed_domains = {
            "github.com",
            "raw.githubusercontent.com",
            "gist.githubusercontent.com",
            "githubusercontent.com",
        }

        if hostname not in allowed_domains:
            return False

        # Check if the hostname is a direct IP address
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return False
        except ValueError:
            # For domain names, resolve the DNS and validate the corresponding IP address
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
