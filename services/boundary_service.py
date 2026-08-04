import httpx
from typing import Optional
from config import BOUNDARY_ADDR, BOUNDARY_TOKEN
from logger import logger, log_json


class BoundaryService:
    """Service for interacting with Boundary API"""

    def __init__(self):
        self.base_url = BOUNDARY_ADDR
        self.token = BOUNDARY_TOKEN

    async def get_credential_path(self, credential_id: str) -> Optional[str]:
        """Fetch vault path from Boundary credential library"""
        url = f"{self.base_url}/v1/credential-libraries/{credential_id}"

        try:
            log_json(logger, "info", "Calling Boundary API", method="GET", data={"url": url, "credential_id": credential_id[:10] + "..."})
            
            async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {self.token}"}
                )

                if response.status_code == 200:
                    data = response.json()
                    vault_path = data.get("attributes", {}).get("path")
                    log_json(logger, "info", "Boundary API call successful", method="GET", data={"vault_path": vault_path})
                    return vault_path
                
                log_json(logger, "error", "Boundary API call failed", method="GET", data={"status_code": response.status_code})
                return None

        except Exception as e:
            log_json(logger, "error", "Boundary API error", method="GET", data={"error": str(e)})
            raise Exception(f"Boundary API error: {str(e)}")


boundary_service = BoundaryService()
