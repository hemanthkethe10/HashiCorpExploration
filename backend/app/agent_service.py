import logging
from typing import Literal

from agent_framework import Agent, Message
from agent_framework.openai import OpenAIChatClient
from pydantic import BaseModel, Field

from app.config import Settings
from app.cosmos import CosmosDbContextResult, CosmosDbCountResult, get_cosmos_db_context, get_cosmos_db_record_count
from app.tools import AGENT_INSTRUCTIONS, create_cosmos_tools

logger = logging.getLogger(__name__)

Role = Literal["user", "assistant", "system"]


class ChatTurn(BaseModel):
    role: Role
    content: str = Field(min_length=1)


class AgentService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._agent = self._create_agent()

    def fetch_db_context(self) -> CosmosDbContextResult:
        return get_cosmos_db_context(
            cosmos_account_name=self._settings.cosmos_account_name,
            mongo_db_name=self._settings.mongo_db_name,
            mongo_collection_name=self._settings.mongo_collection_name,
        )

    def fetch_db_count(self) -> CosmosDbCountResult:
        return get_cosmos_db_record_count(
            cosmos_account_name=self._settings.cosmos_account_name,
            mongo_db_name=self._settings.mongo_db_name,
            mongo_collection_name=self._settings.mongo_collection_name,
        )

    async def chat(self, messages: list[ChatTurn]) -> str:
        chat_messages = [Message(turn.role, [turn.content]) for turn in messages]
        result = await self._agent.run(chat_messages)
        return result.text or ""

    def _create_agent(self) -> Agent:
        client = OpenAIChatClient(
            model=self._settings.openai_model,
            api_key=self._settings.openai_api_key,
        )
        return Agent(
            client=client,
            instructions=AGENT_INSTRUCTIONS,
            tools=create_cosmos_tools(self._settings),
            default_options={"store": False},
        )
