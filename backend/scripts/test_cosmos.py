#!/usr/bin/env python3
"""Verify Cosmos DB access via service principal (AZURE_* env vars)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import load_settings
from app.cosmos import CosmosDbStatus, get_cosmos_db_context


def main() -> int:
    settings = load_settings()
    result = get_cosmos_db_context(
        cosmos_account_name=settings.cosmos_account_name,
        mongo_db_name=settings.mongo_db_name,
        mongo_collection_name=settings.mongo_collection_name,
    )
    print(f"status={result.status.value} available={result.available}")
    if result.message:
        print(f"message={result.message}")
    print(result.context)
    return 0 if result.status == CosmosDbStatus.CONNECTED else 1


if __name__ == "__main__":
    raise SystemExit(main())
