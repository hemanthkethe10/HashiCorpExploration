import json
import logging
import urllib.parse
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import certifi
from azure.identity import DefaultAzureCredential
from pymongo import MongoClient
from pymongo.collection import Collection

from app.config import Settings

logger = logging.getLogger(__name__)

COSMOS_SCOPE = "https://cosmos.azure.com/.default"
MONGO_URI_TEMPLATE = (
    "mongodb://{username}:{password}@{account}.mongo.cosmos.azure.com:10255/"
    "?ssl=true&retrywrites=false&authMechanism=PLAIN"
)
SERVER_SELECTION_TIMEOUT_MS = 5000

UNAVAILABLE_MESSAGE = (
    "Database record unavailable due to authorization or connectivity state."
)
EMPTY_COLLECTION_MESSAGE = "No records found in the database collection."


class CosmosDbStatus(StrEnum):
    CONNECTED = "connected"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class CosmosDbContextResult:
    context: str
    status: CosmosDbStatus
    available: bool
    connected: bool
    message: str | None = None
    checked_at: str | None = None


@dataclass(frozen=True, slots=True)
class CosmosDbCountResult:
    count: int
    database: str
    collection: str
    status: CosmosDbStatus
    available: bool
    connected: bool
    message: str | None = None
    checked_at: str | None = None

    def to_json(self) -> str:
        return json.dumps(
            {
                "database": self.database,
                "collection": self.collection,
                "count": self.count,
                "status": self.status.value,
                "connected": self.connected,
            },
            indent=2,
        )


class CosmosDbService:
    """
    Cosmos DB access via Entra ID.

    One DefaultAzureCredential per process; Azure Identity caches tokens until expiry
    (expected). Each operation opens a new MongoClient. Use force_refresh_token=True
    on test/reload to request a fresh token from Entra.
    """

    def __init__(self, settings: Settings, credential: DefaultAzureCredential | None = None) -> None:
        self._settings = settings
        self._credential = credential or DefaultAzureCredential(
            exclude_interactive_browser_credential=True
        )

    def get_context(self, *, force_refresh_token: bool = False) -> CosmosDbContextResult:
        return self._fetch_sample(force_refresh_token=force_refresh_token)

    def get_record_count(self, *, force_refresh_token: bool = False) -> CosmosDbCountResult:
        return self._fetch_count(force_refresh_token=force_refresh_token)

    def _acquire_token(self, *, force_refresh: bool) -> str:
        logger.info(
            "Acquiring Cosmos token (scope=%s, force_refresh=%s)",
            COSMOS_SCOPE,
            force_refresh,
        )
        token = self._credential.get_token(COSMOS_SCOPE, force_refresh=force_refresh)
        return token.token

    def _connect_collection(self, access_token: str) -> tuple[MongoClient, Collection]:
        account = self._settings.cosmos_account_name
        mongo_uri = MONGO_URI_TEMPLATE.format(
            username=urllib.parse.quote_plus(account),
            password=urllib.parse.quote_plus(access_token),
            account=account,
        )
        logger.info(
            "Connecting to Cosmos DB Mongo API (account=%s, db=%s, collection=%s)",
            account,
            self._settings.mongo_db_name,
            self._settings.mongo_collection_name,
        )
        client = MongoClient(
            mongo_uri,
            serverSelectionTimeoutMS=SERVER_SELECTION_TIMEOUT_MS,
            connectTimeoutMS=SERVER_SELECTION_TIMEOUT_MS,
            tlsCAFile=certifi.where(),
        )
        collection = client[self._settings.mongo_db_name][self._settings.mongo_collection_name]
        return client, collection

    def _fetch_sample(self, *, force_refresh_token: bool) -> CosmosDbContextResult:
        checked_at = datetime.now(UTC).isoformat()
        client: MongoClient | None = None
        try:
            access_token = self._acquire_token(force_refresh=force_refresh_token)
            client, collection = self._connect_collection(access_token)
            record = collection.find_one()

            if not record:
                return CosmosDbContextResult(
                    context=EMPTY_COLLECTION_MESSAGE,
                    status=CosmosDbStatus.EMPTY,
                    available=True,
                    connected=True,
                    message="Connected successfully; collection has no documents.",
                    checked_at=checked_at,
                )

            if "_id" in record:
                record["_id"] = str(record["_id"])
            return CosmosDbContextResult(
                context=json.dumps(record, default=str, indent=2),
                status=CosmosDbStatus.CONNECTED,
                available=True,
                connected=True,
                checked_at=checked_at,
            )
        except Exception as exc:
            logger.warning("Cosmos DB sample fetch failed: %s", exc)
            return CosmosDbContextResult(
                context=UNAVAILABLE_MESSAGE,
                status=CosmosDbStatus.UNAVAILABLE,
                available=False,
                connected=False,
                message=str(exc),
                checked_at=checked_at,
            )
        finally:
            if client is not None:
                client.close()

    def _fetch_count(self, *, force_refresh_token: bool) -> CosmosDbCountResult:
        checked_at = datetime.now(UTC).isoformat()
        client: MongoClient | None = None
        try:
            access_token = self._acquire_token(force_refresh=force_refresh_token)
            client, collection = self._connect_collection(access_token)
            count = collection.count_documents({})
            status = CosmosDbStatus.CONNECTED if count > 0 else CosmosDbStatus.EMPTY
            return CosmosDbCountResult(
                count=count,
                database=self._settings.mongo_db_name,
                collection=self._settings.mongo_collection_name,
                status=status,
                available=True,
                connected=True,
                checked_at=checked_at,
            )
        except Exception as exc:
            logger.warning("Cosmos DB count failed: %s", exc)
            return CosmosDbCountResult(
                count=0,
                database=self._settings.mongo_db_name,
                collection=self._settings.mongo_collection_name,
                status=CosmosDbStatus.UNAVAILABLE,
                available=False,
                connected=False,
                message=str(exc),
                checked_at=checked_at,
            )
        finally:
            if client is not None:
                client.close()
