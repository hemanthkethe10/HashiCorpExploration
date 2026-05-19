import logging
from typing import Literal

from agent_framework import Agent, Message
from agent_framework.openai import OpenAIChatClient
from pydantic import BaseModel, Field

from app.config import Settings
from app.cosmos import CosmosDbContextResult, CosmosDbCountResult, CosmosDbService
from app.tools import AGENT_INSTRUCTIONS, create_cosmos_tools

logger = logging.getLogger(__name__)

Role = Literal["user", "assistant", "system"]


class ChatTurn(BaseModel):
    role: Role
    content: str = Field(min_length=1)


class AgentService:
    def __init__(self, settings: Settings, cosmos: CosmosDbService) -> None:
        self._settings = settings
        self._cosmos = cosmos
        self._agent = self._create_agent()

    def fetch_db_context(self, *, force_refresh_token: bool = False) -> CosmosDbContextResult:
        return self._cosmos.get_context(force_refresh_token=force_refresh_token)

    def fetch_db_count(self, *, force_refresh_token: bool = False) -> CosmosDbCountResult:
        return self._cosmos.get_record_count(force_refresh_token=force_refresh_token)

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
            tools=create_cosmos_tools(self._cosmos),
            default_options={"store": False},
        )
