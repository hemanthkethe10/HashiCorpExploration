from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from config import EXCLUDED_PATHS
from services.boundary_service import boundary_service
from services.vault_service import vault_service
from logger import logger, log_json


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs all incoming requests and responses"""

    async def dispatch(self, request: Request, call_next):
        log_json(
            logger,
            "info",
            f"Incoming request to {request.url.path}",
            method=request.method,
            data={"path": request.url.path, "client": request.client.host if request.client else "unknown"}
        )
        response = await call_next(request)
        log_json(
            logger,
            "info",
            f"Response status {response.status_code}",
            method=request.method,
            data={"path": request.url.path, "status_code": response.status_code}
        )
        return response


class AuthorizationMiddleware(BaseHTTPMiddleware):
    """Validates X-Boundary-Credential and X-API-KEY headers"""

    async def dispatch(self, request: Request, call_next):
        if request.url.path in EXCLUDED_PATHS:
            return await call_next(request)

        credential_id = request.headers.get("X-Boundary-Credential")
        api_key = request.headers.get("X-API-KEY")

        if not credential_id:
            log_json(logger, "warning", "Missing X-Boundary-Credential header", method=request.method, data={"path": request.url.path})
            return JSONResponse(
                status_code=401,
                content={"hasErrors": True, "data": {"error": "X-Boundary-Credential header missing"}}
            )

        if not api_key:
            log_json(logger, "warning", "Missing X-API-KEY header", method=request.method, data={"path": request.url.path})
            return JSONResponse(
                status_code=401,
                content={"hasErrors": True, "data": {"error": "X-API-KEY header missing"}}
            )

        log_json(logger, "info", "Validating credentials", method=request.method, data={"credential_id": credential_id[:10] + "..."})
        
        is_valid, error_msg = await self._validate_credentials(credential_id, api_key)
        if not is_valid:
            log_json(logger, "warning", "Credential validation failed", method=request.method, data={"error": error_msg})
            return JSONResponse(
                status_code=403,
                content={"hasErrors": True, "data": {"error": error_msg}}
            )

        log_json(logger, "info", "Credentials validated successfully", method=request.method, data={"path": request.url.path})
        
        try:
            response = await call_next(request)
            return await self._wrap_response(response)
        except Exception as e:
            log_json(logger, "error", "Internal server error", method=request.method, data={"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"hasErrors": True, "data": {"error": f"Internal server error: {str(e)}"}}
            )

    async def _validate_credentials(self, credential_id: str, api_key: str) -> tuple[bool, str]:
        """Validate credentials through Boundary and Vault"""
        try:
            log_json(logger, "info", "Fetching credential path from Boundary", method="", data={"credential_id": credential_id[:10] + "..."})
            vault_path = await boundary_service.get_credential_path(credential_id)
            if not vault_path:
                log_json(logger, "error", "Invalid credential ID or Boundary API error", method="", data="")
                return False, "Invalid credential ID or Boundary API error"

            log_json(logger, "info", "Creating Vault token", method="", data="")
            vault_token = await vault_service.create_token()
            if not vault_token:
                log_json(logger, "error", "Failed to create Vault token", method="", data="")
                return False, "Failed to create Vault token"

            log_json(logger, "info", "Fetching secret from Vault", method="", data={"vault_path": vault_path})
            secret_data = await vault_service.get_secret(vault_path, vault_token)
            if not secret_data:
                log_json(logger, "error", "Failed to fetch secret from Vault", method="", data="")
                return False, "Failed to fetch secret from Vault"

            stored_api_key = secret_data.get("data", {}).get("data", {}).get("api_key")
            if not stored_api_key:
                log_json(logger, "error", "API key not found in Vault secret", method="", data="")
                return False, "API key not found in Vault secret"

            if stored_api_key != api_key:
                log_json(logger, "warning", "API key mismatch", method="", data="")
                return False, "Invalid API key"

            log_json(logger, "info", "API key validated successfully", method="", data="")
            return True, ""

        except Exception as e:
            log_json(logger, "error", "Validation error", method="", data={"error": str(e)})
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
