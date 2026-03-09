import httpx
from typing import Optional
from config import VAULT_ADDR, VAULT_ROOT_TOKEN, VAULT_TOKEN_POLICIES, VAULT_TOKEN_PERIOD


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
                    return data.get("auth", {}).get("client_token")
                return None
                
        except Exception as e:
            raise Exception(f"Vault token creation error: {str(e)}")

    async def get_secret(self, path: str, token: str) -> Optional[dict]:
        """Fetch secret from Vault using provided path and token"""
        url = f"{self.base_url}/v1/{path}"
        
        try:
            async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
                response = await client.get(
                    url,
                    headers={"X-Vault-Token": token}
                )
                
                if response.status_code == 200:
                    return response.json()
                return None
                
        except Exception as e:
            raise Exception(f"Vault API error: {str(e)}")

    async def validate_token(self, token: str) -> bool:
        """Validate Vault token"""
        url = f"{self.base_url}/v1/auth/token/lookup-self"
        
        try:
            async with httpx.AsyncClient(verify=False, timeout=5.0) as client:
                response = await client.get(
                    url,
                    headers={"X-Vault-Token": token}
                )
                return response.status_code == 200
                
        except Exception:
            return False


vault_service = VaultService()
