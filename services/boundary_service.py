import httpx
from typing import Optional
from config import BOUNDARY_ADDR, BOUNDARY_TOKEN


class BoundaryService:
    """Service for interacting with Boundary API"""

    def __init__(self):
        self.base_url = BOUNDARY_ADDR
        self.token = BOUNDARY_TOKEN

    async def get_credential_path(self, credential_id: str) -> Optional[str]:
        """Fetch vault path from Boundary credential library"""
        url = f"{self.base_url}/v1/credential-libraries/{credential_id}"

        try:
            async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {self.token}"}
                )

                if response.status_code == 200:
                    data = response.json()
                    return data.get("attributes", {}).get("path")
                return None

        except Exception as e:
            raise Exception(f"Boundary API error: {str(e)}")


boundary_service = BoundaryService()
