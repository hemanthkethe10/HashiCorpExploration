import json
import logging
import urllib.parse
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import certifi
from azure.identity import DefaultAzureCredential
from pymongo import MongoClient
from pymongo.collection import Collection

logger = logging.getLogger(__name__)

COSMOS_SCOPE = "https://cosmos.azure.com/.default"
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
    message: str | None = None


@dataclass(frozen=True, slots=True)
class CosmosDbCountResult:
    count: int
    database: str
    collection: str
    status: CosmosDbStatus
    available: bool
    message: str | None = None

    def to_json(self) -> str:
        return json.dumps(
            {
                "database": self.database,
                "collection": self.collection,
                "count": self.count,
                "status": self.status.value,
            },
            indent=2,
        )


def get_azure_credential() -> DefaultAzureCredential:
    """Entra ID credential chain; uses AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET."""
    return DefaultAzureCredential(exclude_interactive_browser_credential=True)


def _build_mongo_uri(*, cosmos_account_name: str, access_token: str) -> str:
    """Build MongoDB URI with Entra access token as the password (URL-encoded)."""
    username = urllib.parse.quote_plus(cosmos_account_name)
    password = urllib.parse.quote_plus(access_token)
    return (
        f"mongodb://{username}:{password}@{cosmos_account_name}.mongo.cosmos.azure.com:10255/"
        "?ssl=true&retrywrites=false&authMechanism=PLAIN"
    )


def _connect_collection(
    *,
    cosmos_account_name: str,
    mongo_db_name: str,
    mongo_collection_name: str,
    credential: DefaultAzureCredential | None = None,
) -> tuple[MongoClient, Collection]:
    cred = credential or get_azure_credential()
    logger.info("Requesting Cosmos DB data-plane token (scope=%s)", COSMOS_SCOPE)
    access_token = cred.get_token(COSMOS_SCOPE).token

    mongo_uri = _build_mongo_uri(
        cosmos_account_name=cosmos_account_name,
        access_token=access_token,
    )

    logger.info(
        "Connecting to Cosmos DB Mongo API (account=%s, db=%s, collection=%s)",
        cosmos_account_name,
        mongo_db_name,
        mongo_collection_name,
    )
    client = MongoClient(
        mongo_uri,
        serverSelectionTimeoutMS=SERVER_SELECTION_TIMEOUT_MS,
        connectTimeoutMS=SERVER_SELECTION_TIMEOUT_MS,
        tlsCAFile=certifi.where(),
    )
    collection = client[mongo_db_name][mongo_collection_name]
    return client, collection


def _serialize_record(record: dict[str, Any]) -> str:
    if "_id" in record:
        record["_id"] = str(record["_id"])
    return json.dumps(record, default=str, indent=2)


def get_cosmos_db_context(
    *,
    cosmos_account_name: str,
    mongo_db_name: str = "debugging",
    mongo_collection_name: str = "data",
    credential: DefaultAzureCredential | None = None,
) -> CosmosDbContextResult:
    """Acquire an Entra ID token, connect via Mongo API, and return one sample document."""
    client: MongoClient | None = None
    try:
        client, collection = _connect_collection(
            cosmos_account_name=cosmos_account_name,
            mongo_db_name=mongo_db_name,
            mongo_collection_name=mongo_collection_name,
            credential=credential,
        )
        record = collection.find_one()

        if not record:
            return CosmosDbContextResult(
                context=EMPTY_COLLECTION_MESSAGE,
                status=CosmosDbStatus.EMPTY,
                available=False,
                message="Collection is reachable but contains no documents.",
            )

        return CosmosDbContextResult(
            context=_serialize_record(record),
            status=CosmosDbStatus.CONNECTED,
            available=True,
        )
    except Exception as exc:
        logger.warning("Cosmos DB connection/auth failed: %s", exc)
        return CosmosDbContextResult(
            context=UNAVAILABLE_MESSAGE,
            status=CosmosDbStatus.UNAVAILABLE,
            available=False,
            message=str(exc),
        )
    finally:
        if client is not None:
            client.close()


def get_cosmos_db_record_count(
    *,
    cosmos_account_name: str,
    mongo_db_name: str = "debugging",
    mongo_collection_name: str = "data",
    credential: DefaultAzureCredential | None = None,
) -> CosmosDbCountResult:
    """Return the total document count for the Cosmos DB collection."""
    client: MongoClient | None = None
    try:
        client, collection = _connect_collection(
            cosmos_account_name=cosmos_account_name,
            mongo_db_name=mongo_db_name,
            mongo_collection_name=mongo_collection_name,
            credential=credential,
        )
        count = collection.count_documents({})
        status = CosmosDbStatus.CONNECTED if count > 0 else CosmosDbStatus.EMPTY

        return CosmosDbCountResult(
            count=count,
            database=mongo_db_name,
            collection=mongo_collection_name,
            status=status,
            available=True,
        )
    except Exception as exc:
        logger.warning("Cosmos DB count failed: %s", exc)
        return CosmosDbCountResult(
            count=0,
            database=mongo_db_name,
            collection=mongo_collection_name,
            status=CosmosDbStatus.UNAVAILABLE,
            available=False,
            message=str(exc),
        )
    finally:
        if client is not None:
            client.close()
