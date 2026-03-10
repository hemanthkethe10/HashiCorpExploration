from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import httpx
from typing import Optional
from datetime import datetime
import base64
import json

from config import (
    VAULT_ADDR,
    VAULT_NAMESPACE,
    PROVIDER_NAME,
    CLIENT_ID,
    CLIENT_SECRET,
    REDIRECT_URI,
    token_storage
)
from middleware import AuthorizationMiddleware, RequestLoggingMiddleware
from logger import logger, log_json

app = FastAPI(title="FAST API Server For HashiCorp")
app.add_middleware(AuthorizationMiddleware)
app.add_middleware(RequestLoggingMiddleware)


@app.get("/health")
async def health():
    """Health check endpoint"""
    log_json(logger, "info", "Health check called", method="GET", data="")
    return {"status": "ok"}


@app.get("/auth/login")
async def initiate_oidc_login():
    """
    Initiate OIDC login flow.
    Returns the authorization URL to redirect users to Vault.
    """
    log_json(logger, "info", "Initiating OIDC login flow", method="GET", data="")
    
    namespace_path = f"{VAULT_NAMESPACE}/" if VAULT_NAMESPACE else ""
    auth_url = f"{VAULT_ADDR}/ui/vault/{namespace_path}identity/oidc/provider/{PROVIDER_NAME}/authorize"
    
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "openid",
        "state": "random_state_value"
    }

    param_string = "&".join([f"{k}={v}" for k, v in params.items()])
    full_auth_url = f"{auth_url}?{param_string}"

    log_json(logger, "info", "OIDC authorization URL generated", method="GET", data={"provider": PROVIDER_NAME})
    
    return JSONResponse(
        content={
            "message": "Redirect user to this URL to start OIDC flow",
            "authorization_url": full_auth_url
        }
    )


@app.get("/auth/callback")
async def oidc_callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    """
    OIDC redirect callback endpoint.
    Exchanges authorization code for tokens and stores them in memory.
    """
    if error:
        log_json(logger, "error", f"OIDC callback error: {error}", method="GET", data={"error": error})
        raise HTTPException(status_code=400, detail=f"OIDC error: {error}")
    
    if not code:
        log_json(logger, "error", "Authorization code not provided", method="GET", data="")
        raise HTTPException(status_code=400, detail="Authorization code not provided")
    
    log_json(logger, "info", "Processing OIDC callback", method="GET", data={"state": state})
    
    namespace_path = f"v1/{VAULT_NAMESPACE}" if VAULT_NAMESPACE else "v1"
    token_url = f"{VAULT_ADDR}/{namespace_path}/identity/oidc/provider/{PROVIDER_NAME}/token"
    
    async with httpx.AsyncClient(verify=False) as client:
        try:
            # Prepare client authentication using client_secret_basic method
            auth_string = f"{CLIENT_ID}:{CLIENT_SECRET}"
            auth_bytes = auth_string.encode('utf-8')
            auth_b64 = base64.b64encode(auth_bytes).decode('utf-8')
            
            log_json(logger, "info", "Exchanging authorization code for tokens", method="POST", data={"token_url": token_url})
            
            # Exchange code for tokens
            token_response = await client.post(
                token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": REDIRECT_URI,
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Basic {auth_b64}"
                }
            )
            
            if token_response.status_code != 200:
                log_json(logger, "error", "Token exchange failed", method="POST", data={"status_code": token_response.status_code, "response": token_response.text})
                raise HTTPException(
                    status_code=token_response.status_code,
                    detail=f"Token exchange failed: {token_response.text}"
                )
            
            token_data = token_response.json()
            log_json(logger, "info", "Token exchange successful", method="POST", data={"token_type": token_data.get("token_type")})
            
            # Store tokens in memory
            token_storage["access_token"] = token_data.get("access_token")
            token_storage["id_token"] = token_data.get("id_token")
            token_storage["refresh_token"] = token_data.get("refresh_token")
            token_storage["token_type"] = token_data.get("token_type", "Bearer")
            token_storage["expires_in"] = token_data.get("expires_in")
            token_storage["stored_at"] = datetime.utcnow().isoformat()
            
            # Fetch userinfo to test the access token
            userinfo = await fetch_userinfo(token_storage["access_token"])
            token_storage["userinfo"] = userinfo
            
            log_json(logger, "info", "OIDC authentication completed successfully", method="GET", data={"expires_in": token_storage["expires_in"]})
            
            return JSONResponse(
                status_code=200,
                content={
                    "message": "OIDC authentication successful",
                    "token_stored": True,
                    "token_type": token_storage["token_type"],
                    "expires_in": token_storage["expires_in"],
                    "userinfo": userinfo
                }
            )
            
        except httpx.RequestError as e:
            log_json(logger, "error", "Request failed during token exchange", method="POST", data={"error": str(e)})
            raise HTTPException(status_code=500, detail=f"Request failed: {str(e)}")
        except Exception as e:
            log_json(logger, "error", "Unexpected error during OIDC callback", method="GET", data={"error": str(e)})
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@app.get("/auth/tokens")
async def get_tokens(show_secrets: bool = False):
    """
    Get stored token information.
    
    Parameters:
    - show_secrets: If true, shows actual token values. Default is false (masked).
    """
    if not token_storage["access_token"]:
        return JSONResponse(
            status_code=404,
            content={"message": "No tokens stored. Complete the OIDC flow first via /auth/login"}
        )
    
    def mask_token(token):
        """Mask token showing only first and last 10 characters"""
        if not token or not show_secrets:
            if token and len(token) > 20:
                return f"{token[:10]}...{token[-10:]}"
            return "***MASKED***"
        return token
    
    return JSONResponse(
        content={
            "tokens": {
                "access_token": mask_token(token_storage["access_token"]),
                "id_token": mask_token(token_storage["id_token"]),
                "refresh_token": mask_token(token_storage["refresh_token"]),
                "token_type": token_storage["token_type"]
            },
            "metadata": {
                "expires_in": token_storage["expires_in"],
                "stored_at": token_storage["stored_at"]
            },
            "userinfo": token_storage["userinfo"],
            "note": "Use ?show_secrets=true to see full token values"
        }
    )


@app.get("/auth/tokens/decode-id-token")
async def decode_id_token():
    """
    Decode the ID token (JWT) to show its claims.
    """
    if not token_storage["id_token"]:
        return JSONResponse(
            status_code=404,
            content={"message": "No ID token stored"}
        )
    
    try:
        # Split the JWT into parts
        parts = token_storage["id_token"].split('.')
        if len(parts) != 3:
            raise ValueError("Invalid JWT format")
        
        # Decode header and payload
        def decode_base64url(data):
            padding = 4 - len(data) % 4
            if padding != 4:
                data += '=' * padding
            return base64.urlsafe_b64decode(data)
        
        header = json.loads(decode_base64url(parts[0]))
        payload = json.loads(decode_base64url(parts[1]))
        
        return JSONResponse(
            content={
                "header": header,
                "payload": payload,
                "note": "The signature is not decoded (it's binary data used for verification)"
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to decode ID token: {str(e)}")


@app.delete("/auth/tokens")
async def clear_tokens():
    """Clear all stored tokens from memory"""
    token_storage["access_token"] = None
    token_storage["id_token"] = None
    token_storage["refresh_token"] = None
    token_storage["token_type"] = None
    token_storage["expires_in"] = None
    token_storage["stored_at"] = None
    token_storage["userinfo"] = None
    
    return JSONResponse(
        content={"message": "All tokens cleared from memory"}
    )


async def fetch_userinfo(access_token: str):
    """
    Fetch user information using the access token.
    The access token is a Vault batch token that provides read access to the userinfo endpoint.
    """
    log_json(logger, "info", "Fetching userinfo", method="GET", data="")
    
    namespace_path = f"v1/{VAULT_NAMESPACE}" if VAULT_NAMESPACE else "v1"
    userinfo_url = f"{VAULT_ADDR}/{namespace_path}/identity/oidc/provider/{PROVIDER_NAME}/userinfo"
    
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            userinfo_url,
            headers={
                "Authorization": f"Bearer {access_token}"
            }
        )
        
        if response.status_code != 200:
            log_json(logger, "error", "Failed to fetch userinfo", method="GET", data={"status_code": response.status_code, "response": response.text})
            return {
                "error": f"Failed to fetch userinfo: {response.status_code}",
                "details": response.text
            }
        
        log_json(logger, "info", "Userinfo fetched successfully", method="GET", data="")
        return response.json()


@app.get("/vault/secrets/{path:path}")
async def read_secret(path: str, vault_token: Optional[str] = None, use_oidc_token: bool = False):
    """
    Read a secret from Vault at the specified path.
    
    Parameters:
    - path: The secret path (e.g., "secret/data/myapp/config")
    - vault_token: A Vault token with permission to read secrets (query parameter)
    - use_oidc_token: If true, attempts to use the stored OIDC access token (will likely fail)
    
    Usage:
    - /vault/secrets/secret/data/myapp/config?vault_token=YOUR_VAULT_TOKEN
    - /vault/secrets/kv/data/myapp/db?vault_token=YOUR_VAULT_TOKEN
    
    Note: The OIDC access token typically doesn't have permission to read secrets.
    You need a proper Vault token obtained through vault login.
    """
    # Determine which token to use
    if use_oidc_token:
        if not token_storage["access_token"]:
            raise HTTPException(
                status_code=400,
                detail="No OIDC access token stored. Complete the OIDC flow first."
            )
        auth_token = token_storage["access_token"]
        token_type = "OIDC access token (likely insufficient permissions)"
    elif vault_token:
        auth_token = vault_token
        token_type = "Vault token"
    else:
        raise HTTPException(
            status_code=400,
            detail="Either vault_token query parameter or use_oidc_token=true is required"
        )
    
    # Build the secret URL
    secret_url = f"{VAULT_ADDR}/v1/{path}"
    
    async with httpx.AsyncClient(verify=False) as client:
        try:
            response = await client.get(
                secret_url,
                headers={
                    "X-Vault-Token": auth_token,
                    "X-Vault-Request": "true"
                }
            )
            
            if response.status_code == 403:
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "Permission denied",
                        "message": f"The {token_type} doesn't have permission to read this secret",
                        "path": path,
                        "help": "Use a Vault token with appropriate policies. Get one with: vault login"
                    }
                )
            
            if response.status_code == 404:
                return JSONResponse(
                    status_code=404,
                    content={
                        "error": "Secret not found",
                        "path": path,
                        "help": "Check the path. For KV v2, use: secret/data/path (not secret/path)"
                    }
                )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to read secret: {response.text}"
                )
            
            data = response.json()
            
            return JSONResponse(
                content={
                    "path": path,
                    "data": data,
                    "token_used": token_type
                }
            )
            
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"Request failed: {str(e)}")


@app.post("/vault/secrets/{path:path}")
async def write_secret(path: str, secret_data: dict, vault_token: Optional[str] = None):
    """
    Write a secret to Vault at the specified path.
    
    Parameters:
    - path: The secret path (e.g., "secret/data/myapp/config")
    - secret_data: JSON object containing the secret data
    - vault_token: A Vault token with permission to write secrets
    
    Usage:
    POST /vault/secrets/secret/data/myapp/config?vault_token=YOUR_VAULT_TOKEN
    Body: {"data": {"username": "admin", "password": "secret123"}}
    
    Note: For KV v2 secrets engine, wrap your data in a "data" key.
    """
    if not vault_token:
        raise HTTPException(
            status_code=400,
            detail="vault_token query parameter required"
        )
    
    secret_url = f"{VAULT_ADDR}/v1/{path}"
    
    async with httpx.AsyncClient(verify=False) as client:
        try:
            response = await client.post(
                secret_url,
                json=secret_data,
                headers={
                    "X-Vault-Token": vault_token,
                    "X-Vault-Request": "true"
                }
            )
            
            if response.status_code == 403:
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "Permission denied",
                        "message": "The Vault token doesn't have permission to write this secret",
                        "path": path
                    }
                )
            
            if response.status_code not in [200, 204]:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to write secret: {response.text}"
                )
            
            return JSONResponse(
                content={
                    "message": "Secret written successfully",
                    "path": path
                }
            )
            
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"Request failed: {str(e)}")


@app.get("/vault/secrets")
async def list_secrets(path: str = "secret/metadata", vault_token: Optional[str] = None):
    """
    List secrets at the specified path.
    
    Parameters:
    - path: The path to list (default: "secret/metadata")
    - vault_token: A Vault token with permission to list secrets
    
    Usage:
    - /vault/secrets?vault_token=YOUR_VAULT_TOKEN
    - /vault/secrets?path=secret/metadata/myapp&vault_token=YOUR_VAULT_TOKEN
    
    Note: For KV v2, use the metadata path to list secrets.
    """
    if not vault_token:
        raise HTTPException(
            status_code=400,
            detail="vault_token query parameter required"
        )
    
    list_url = f"{VAULT_ADDR}/v1/{path}"
    
    async with httpx.AsyncClient(verify=False) as client:
        try:
            response = await client.request(
                "LIST",
                list_url,
                headers={
                    "X-Vault-Token": vault_token,
                    "X-Vault-Request": "true"
                }
            )
            
            if response.status_code == 403:
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "Permission denied",
                        "message": "The Vault token doesn't have permission to list secrets at this path",
                        "path": path
                    }
                )
            
            if response.status_code == 404:
                return JSONResponse(
                    status_code=404,
                    content={
                        "error": "Path not found",
                        "path": path,
                        "help": "The path doesn't exist or contains no secrets"
                    }
                )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to list secrets: {response.text}"
                )
            
            data = response.json()
            
            return JSONResponse(
                content={
                    "path": path,
                    "keys": data.get("data", {}).get("keys", [])
                }
            )
            
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"Request failed: {str(e)}")
