#!/usr/bin/env python3
"""Verify Cosmos DB access via service principal (AZURE_* env vars)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import load_settings
from app.cosmos import CosmosDbService, CosmosDbStatus


def main() -> int:
    settings = load_settings()
    cosmos = CosmosDbService(settings)
    result = cosmos.get_context(force_refresh_token=True)
    print(f"status={result.status.value} connected={result.connected} available={result.available}")
    if result.message:
        print(f"message={result.message}")
    print(result.context)
    return 0 if result.status == CosmosDbStatus.CONNECTED else 1


if __name__ == "__main__":
    raise SystemExit(main())
