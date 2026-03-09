from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from config import EXCLUDED_PATHS
from services.boundary_service import boundary_service
from services.vault_service import vault_service


class AuthorizationMiddleware(BaseHTTPMiddleware):
    """Validates X-Boundary-Credential and X-API-KEY headers"""

    async def dispatch(self, request: Request, call_next):
        if request.url.path in EXCLUDED_PATHS:
            return await call_next(request)

        credential_id = request.headers.get("X-Boundary-Credential")
        api_key = request.headers.get("X-API-KEY")

        if not credential_id:
            return JSONResponse(
                status_code=401,
                content={"hasErrors": True, "data": {"error": "X-Boundary-Credential header missing"}}
            )

        if not api_key:
            return JSONResponse(
                status_code=401,
                content={"hasErrors": True, "data": {"error": "X-API-KEY header missing"}}
            )

        is_valid, error_msg = await self._validate_credentials(credential_id, api_key)
        if not is_valid:
            return JSONResponse(
                status_code=403,
                content={"hasErrors": True, "data": {"error": error_msg}}
            )

        try:
            response = await call_next(request)
            return await self._wrap_response(response)
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"hasErrors": True, "data": {"error": f"Internal server error: {str(e)}"}}
            )

    async def _validate_credentials(self, credential_id: str, api_key: str) -> tuple[bool, str]:
        """Validate credentials through Boundary and Vault"""
        try:
            vault_path = await boundary_service.get_credential_path(credential_id)
            if not vault_path:
                return False, "Invalid credential ID or Boundary API error"

            vault_token = await vault_service.create_token()
            if not vault_token:
                return False, "Failed to create Vault token"

            secret_data = await vault_service.get_secret(vault_path, vault_token)
            if not secret_data:
                return False, "Failed to fetch secret from Vault"

            stored_api_key = secret_data.get("data", {}).get("data", {}).get("api_key")
            if not stored_api_key:
                return False, "API key not found in Vault secret"

            if stored_api_key != api_key:
                return False, "Invalid API key"

            return True, ""

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
                return JSONResponse(status_code=response.status_code, content=wrapped)
            except:
                return response
        return response
