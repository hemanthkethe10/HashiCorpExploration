from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import httpx
from config import VAULT_ADDR, VAULT_AUTH_PATH, EXCLUDED_PATHS


class AuthorizationMiddleware(BaseHTTPMiddleware):
    """Validates authorization header against Vault for each request"""

    async def dispatch(self, request: Request, call_next):
        # Skip auth for excluded paths
        if request.url.path in EXCLUDED_PATHS:
            return await call_next(request)

        # Extract authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return JSONResponse(
                status_code=401,
                content={
                    "hasErrors": True,
                    "data": {"error": "Authorization header missing"}
                }
            )

        # Extract token from Bearer scheme
        token = self._extract_token(auth_header)
        if not token:
            return JSONResponse(
                status_code=401,
                content={
                    "hasErrors": True,
                    "data": {"error": "Invalid authorization format. Use: Bearer <token>"}
                }
            )

        # Validate token against Vault
        is_valid, error_msg = await self._validate_token(token)
        if not is_valid:
            return JSONResponse(
                status_code=403,
                content={
                    "hasErrors": True,
                    "data": {"error": error_msg}
                }
            )

        # Process request and wrap response
        try:
            response = await call_next(request)
            return await self._wrap_response(response)
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    "hasErrors": True,
                    "data": {"error": f"Internal server error: {str(e)}"}
                }
            )

    def _extract_token(self, auth_header: str) -> str:
        """Extract token from Authorization header"""
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
        return ""

    async def _validate_token(self, token: str) -> tuple[bool, str]:
        """Validate token against Vault"""
        vault_url = f"{VAULT_ADDR}/{VAULT_AUTH_PATH}"
        
        try:
            async with httpx.AsyncClient(verify=False, timeout=5.0) as client:
                response = await client.get(
                    vault_url,
                    headers={"X-Vault-Token": token}
                )
                
                if response.status_code == 200:
                    return True, ""
                elif response.status_code == 403:
                    return False, "Invalid or expired token"
                else:
                    return False, f"Token validation failed: {response.status_code}"
                    
        except httpx.TimeoutException:
            return False, "Vault validation timeout"
        except httpx.RequestError as e:
            return False, f"Vault connection error: {str(e)}"
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    async def _wrap_response(self, response: Response) -> Response:
        """Wrap successful responses in standard format"""
        if response.status_code < 400:
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            
            try:
                import json
                data = json.loads(body.decode())
                wrapped = {"hasErrors": False, "data": data}
                return JSONResponse(
                    status_code=response.status_code,
                    content=wrapped
                )
            except:
                return response
        return response
