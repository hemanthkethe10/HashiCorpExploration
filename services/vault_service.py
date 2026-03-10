import httpx
from typing import Optional
from config import VAULT_ADDR, VAULT_ROOT_TOKEN, VAULT_TOKEN_POLICIES, VAULT_TOKEN_PERIOD
from logger import logger, log_json


class VaultService:
    """Service for interacting with Vault API"""

    def __init__(self):
        self.base_url = VAULT_ADDR
        self.root_token = VAULT_ROOT_TOKEN

    async def create_token(self) -> Optional[str]:
        """Create a new Vault token with configured policies"""
        url = f"{self.base_url}/v1/auth/token/create"
        
        payload = {
            "policies": VAULT_TOKEN_POLICIES,
            "period": VAULT_TOKEN_PERIOD,
            "no_parent": True
        }
        
        try:
            log_json(logger, "info", "Creating Vault token", method="POST", data={"policies": VAULT_TOKEN_POLICIES, "period": VAULT_TOKEN_PERIOD})
            
            async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={
                        "X-Vault-Token": self.root_token,
                        "Content-Type": "application/json"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    token = data.get("auth", {}).get("client_token")
                    log_json(logger, "info", "Vault token created successfully", method="POST", data="")
                    return token
                
                log_json(logger, "error", "Vault token creation failed", method="POST", data={"status_code": response.status_code})
                return None
                
        except Exception as e:
            log_json(logger, "error", "Vault token creation error", method="POST", data={"error": str(e)})
            raise Exception(f"Vault token creation error: {str(e)}")

    async def get_secret(self, path: str, token: str) -> Optional[dict]:
        """Fetch secret from Vault using provided path and token"""
        url = f"{self.base_url}/v1/{path}"
        
        try:
            log_json(logger, "info", "Fetching secret from Vault", method="GET", data={"path": path})
            
            async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
                response = await client.get(
                    url,
                    headers={"X-Vault-Token": token}
                )
                
                if response.status_code == 200:
                    log_json(logger, "info", "Secret fetched successfully", method="GET", data={"path": path})
                    return response.json()
                
                log_json(logger, "error", "Failed to fetch secret", method="GET", data={"status_code": response.status_code, "path": path})
                return None
                
        except Exception as e:
            log_json(logger, "error", "Vault API error", method="GET", data={"error": str(e)})
            raise Exception(f"Vault API error: {str(e)}")

    async def validate_token(self, token: str) -> bool:
        """Validate Vault token"""
        url = f"{self.base_url}/v1/auth/token/lookup-self"
        
        try:
            log_json(logger, "info", "Validating Vault token", method="GET", data="")
            
            async with httpx.AsyncClient(verify=False, timeout=5.0) as client:
                response = await client.get(
                    url,
                    headers={"X-Vault-Token": token}
                )
                
                is_valid = response.status_code == 200
                log_json(logger, "info", f"Token validation result: {is_valid}", method="GET", data={"valid": is_valid})
                return is_valid
                
        except Exception as e:
            log_json(logger, "error", "Token validation error", method="GET", data={"error": str(e)})
            return False


vault_service = VaultService()
