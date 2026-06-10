import ipaddress
import socket
from urllib.parse import urlparse

import bcrypt


def hash_passcode(passcode: str) -> str:
    """平文のパスコードをハッシュ化する"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(passcode.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_passcode(plain_passcode: str, hashed_passcode: str) -> bool:
    """平文のパスコードとハッシュ化されたパスコードが一致するか検証する"""
    try:
        return bcrypt.checkpw(plain_passcode.encode('utf-8'), hashed_passcode.encode('utf-8'))
    except Exception:
        return False


def is_safe_url(url: str) -> bool:
    """SSRF対策: 許可されたドメイン（GitHub等）のみを許可し、さらにローカルやプライベートIPへのリクエストを遮断する."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        # CodeQLがサニタイザーとして認識しやすいように、許可されたドメインのホワイトリストチェックを行う
        # 実用上、カスタムテンプレートの共有先はGitHub（またはRaw/Gist）に限定されます
        allowed_domains = {
            'github.com',
            'raw.githubusercontent.com',
            'gist.githubusercontent.com',
            'githubusercontent.com'
        }

        domain_matched = False
        for allowed in allowed_domains:
            if hostname == allowed or hostname.endswith('.' + allowed):
                domain_matched = True
                break

        if not domain_matched:
            return False

        # ホスト名が直接IPアドレスの場合のチェック
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return False
        except ValueError:
            # ドメイン名の場合はDNS解決を行い、そのIPアドレスを検証する
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


