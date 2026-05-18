import logging
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.agent_service import AgentService, ChatTurn
from app.config import Settings, load_settings
from app.cosmos import CosmosDbContextResult, CosmosDbCountResult
from app.graph_pim import GraphPimClient
from app.routers.pim import router as pim_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    messages: list[ChatTurn] = Field(min_length=1)


class ChatResponse(BaseModel):
    content: str


class DbContextResponse(BaseModel):
    context: str
    status: Literal["connected", "empty", "unavailable"]
    available: bool
    message: str | None = None


class DbCountResponse(BaseModel):
    count: int
    database: str
    collection: str
    status: Literal["connected", "empty", "unavailable"]
    available: bool
    message: str | None = None


def get_agent_service(request: Request) -> AgentService:
    service = getattr(request.app.state, "agent_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Agent service is not initialized.")
    return service


def create_app(settings: Settings) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.agent_service = AgentService(settings)
        app.state.graph_pim_client = GraphPimClient(settings)
        logger.info("Agent ready (OpenAI + Cosmos DB tools + Graph PIM).")
        yield
        app.state.agent_service = None
        app.state.graph_pim_client = None

    application = FastAPI(title="RA-Agent Chat API", lifespan=lifespan)
    application.include_router(pim_router)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return application


def _to_db_response(result: CosmosDbContextResult) -> DbContextResponse:
    return DbContextResponse(
        context=result.context,
        status=result.status.value,
        available=result.available,
        message=result.message,
    )


def _to_count_response(result: CosmosDbCountResult) -> DbCountResponse:
    return DbCountResponse(
        count=result.count,
        database=result.database,
        collection=result.collection,
        status=result.status.value,
        available=result.available,
        message=result.message,
    )


settings = load_settings()
app = create_app(settings)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/db-context", response_model=DbContextResponse)
async def get_db_context(
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> DbContextResponse:
    return _to_db_response(service.fetch_db_context())


@app.post("/api/db-context/reload", response_model=DbContextResponse)
async def reload_db_context(
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> DbContextResponse:
    """Re-run token acquisition and Cosmos fetch (e.g. after PIM activation)."""
    return _to_db_response(service.fetch_db_context())


@app.get("/api/db-count", response_model=DbCountResponse)
async def get_db_count(
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> DbCountResponse:
    return _to_count_response(service.fetch_db_count())


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> ChatResponse:
    if body.messages[-1].role != "user":
        raise HTTPException(status_code=400, detail="Last message must be from the user.")
    content = await service.chat(body.messages)
    return ChatResponse(content=content)


def run() -> None:
    settings = load_settings()
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    run()
