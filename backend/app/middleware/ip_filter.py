import ipaddress

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app import config


class IPLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # ALLOWED_IPS が空の場合は制限を行わない（全許可）
        if not config.ALLOWED_IPS:
            return await call_next(request)

        # X-Forwarded-For ヘッダーからクライアントIPをパース
        client_ip_str = None
        xff = request.headers.get("x-forwarded-for")
        if xff:
            parts = [p.strip() for p in xff.split(",")]
            if parts:
                client_ip_str = parts[0]

        # X-Forwarded-For がない場合は request.client.host を使用
        if not client_ip_str:
            client_ip_str = request.client.host if request.client else None

        if not client_ip_str:
            return JSONResponse(
                status_code=403,
                content={"detail": "Forbidden: Client IP not determined"},
            )

        try:
            client_ip = ipaddress.ip_address(client_ip_str)
        except ValueError:
            return JSONResponse(
                status_code=403,
                content={"detail": "Forbidden: Invalid client IP address"},
            )

        # 許可されたネットワークに属しているかチェック
        allowed = False
        for network in config.ALLOWED_IPS:
            if client_ip in network:
                allowed = True
                break

        if not allowed:
            return JSONResponse(
                status_code=403,
                content={"detail": "Forbidden: IP address not allowed"},
            )

        return await call_next(request)
