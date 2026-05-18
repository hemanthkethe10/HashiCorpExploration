from collections.abc import Sequence

from agent_framework import tool

from app.config import Settings
from app.cosmos import get_cosmos_db_context, get_cosmos_db_record_count

AGENT_INSTRUCTIONS = """You are RA-Agent-001.

When the user asks about onboarding, account, or database data:
- Use fetch_cosmos_database_record to load a sample document from Azure Cosmos DB.
- Use fetch_cosmos_database_record_count when the user asks how many records, rows,
  documents, or entries exist in the database (or similar count questions).

Summarize tool results in clear, concise language. For count questions, state the
exact count returned by the tool.

If a tool reports that data is unavailable, explain that Cosmos DB could not be
reached (for example, Entra credentials or PIM role not active). Do not invent data.
"""


def create_cosmos_tools(settings: Settings) -> Sequence[object]:
    @tool(approval_mode="never_require")
    def fetch_cosmos_database_record() -> str:
        """Fetch a sample onboarding record from Azure Cosmos DB (Mongo API) via Entra ID."""
        result = get_cosmos_db_context(
            cosmos_account_name=settings.cosmos_account_name,
            mongo_db_name=settings.mongo_db_name,
            mongo_collection_name=settings.mongo_collection_name,
        )
        return result.context

    @tool(approval_mode="never_require")
    def fetch_cosmos_database_record_count() -> str:
        """Return the total number of documents in the Azure Cosmos DB collection."""
        result = get_cosmos_db_record_count(
            cosmos_account_name=settings.cosmos_account_name,
            mongo_db_name=settings.mongo_db_name,
            mongo_collection_name=settings.mongo_collection_name,
        )
        if not result.available:
            return (
                "Database count unavailable due to authorization or connectivity state."
                + (f" Detail: {result.message}" if result.message else "")
            )
        return result.to_json()

    return [fetch_cosmos_database_record, fetch_cosmos_database_record_count]
