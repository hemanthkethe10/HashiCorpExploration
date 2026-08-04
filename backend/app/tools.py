import logging
from collections.abc import Sequence

from agent_framework import tool

from app.cosmos import CosmosDbService

logger = logging.getLogger(__name__)

AGENT_INSTRUCTIONS = """You are the Azure Entra PIM Access Check Agent.

When the user asks about onboarding, account, or database data:
- You MUST call fetch_cosmos_database_record or fetch_cosmos_database_record_count
  before answering. Do not use earlier chat messages as a source of database facts.
- Use fetch_cosmos_database_record for sample record content.
- Use fetch_cosmos_database_record_count for how many records/documents exist.

Summarize tool results in clear, concise language.

If a tool returns that data is unavailable, say Cosmos DB could not be reached.
Do not invent database values.
"""


def create_cosmos_tools(cosmos: CosmosDbService) -> Sequence[object]:
    @tool(approval_mode="never_require")
    def fetch_cosmos_database_record() -> str:
        """Fetch a sample onboarding record from Azure Cosmos DB (Mongo API) via Entra ID."""
        logger.info("Agent tool invoked: fetch_cosmos_database_record")
        result = cosmos.get_context(force_refresh_token=False)
        return result.context

    @tool(approval_mode="never_require")
    def fetch_cosmos_database_record_count() -> str:
        """Return the total number of documents in the Azure Cosmos DB collection."""
        logger.info("Agent tool invoked: fetch_cosmos_database_record_count")
        result = cosmos.get_record_count(force_refresh_token=False)
        if not result.connected:
            return (
                "Database count unavailable due to authorization or connectivity state."
                + (f" Detail: {result.message}" if result.message else "")
            )
        return result.to_json()

    return [fetch_cosmos_database_record, fetch_cosmos_database_record_count]
