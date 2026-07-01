"""
Agent server entry point.
Run with: python -m src.agent
"""

import asyncio
import json
import os
import sys

import uvicorn
from fastapi import Request, Body, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.apps import A2AFastAPIApplication
from a2a.types import AgentCard, AgentCapabilities, AgentProvider, AgentSkill

from pathlib import Path

from .executor import AgentExecutor
from src.config.settings import settings
from src.middleware.claims_middleware import OtelContextMiddleware
from src.utils.health import get_health_checker
from cams_otel_lib import Logger as logger, Otel_Client, otel_trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor


def _read_agent_config_field(field: str, default: str = "N/A") -> str:
    """Read a top-level field from agent_config.json. APP_CONFIG_PATH takes priority."""
    try:
        ext = os.getenv("APP_CONFIG_PATH")
        if ext:
            p = Path(ext)
            if p.exists():
                with open(p) as f:
                    data = json.load(f)
                    # Support both top-level and nested runtime_context
                    return data.get(field) or data.get("runtime_context", {}).get(field, default)
        config_path = Path(__file__).parent.parent / "config" / "agent_config.json"
        with open(config_path) as f:
            data = json.load(f)
            return data.get(field) or data.get("runtime_context", {}).get(field, default)
    except Exception:
        return default


try:
    from src.middleware.rate_limiting import RateLimitMiddleware, get_rate_limiter
    RATE_LIMITING_AVAILABLE = True
except ImportError:
    RateLimitMiddleware = None
    get_rate_limiter = None
    RATE_LIMITING_AVAILABLE = False

try:
    from src.utils.metrics import get_metrics_collector
    METRICS_AVAILABLE = True
except ImportError:
    get_metrics_collector = None
    METRICS_AVAILABLE = False


if METRICS_AVAILABLE:
    metrics_collector = get_metrics_collector()


@otel_trace
def create_agent_card() -> AgentCard:
    """Build the A2A agent card from agent_config.json agent_definition."""
    from src.config.cams_config_adapter import CAMSConfigAdapter

    agent_def = {}
    capabilities_cfg = {}
    provider_cfg = {}
    skills_cfg = []
    raw_version = "1.0.0"
    try:
        ext = os.getenv("APP_CONFIG_PATH")
        cfg_path = Path(ext) if ext else Path(__file__).parent.parent / "config" / "agent_config.json"
        if cfg_path.exists():
            import json as _json
            raw = _json.loads(cfg_path.read_text())
            adapter = CAMSConfigAdapter(raw)
            agent_def = adapter.get_agent_definition()
            capabilities_cfg = agent_def.get("capabilities", {})
            provider_cfg = agent_def.get("provider", {})
            skills_cfg = agent_def.get("skills", [])
            raw_version = agent_def.get("version", "1.0.0")
    except Exception as e:
        logger.warning(f"Could not load agent_definition from config, using defaults: {e}")

    if skills_cfg:
        skills = [
            AgentSkill(
                id=s.get("id", f"skill_{i}"),
                name=s.get("name", f"Skill {i}"),
                description=s.get("description", ""),
                tags=s.get("tags", []),
                examples=s.get("examples", []),
                input_modes=s.get("inputModes", ["text/plain"]),
                output_modes=s.get("outputModes", ["text/plain"]),
            )
            for i, s in enumerate(skills_cfg)
        ]
    else:
        skills = [
            AgentSkill(
                id="search_and_answer",
                name="Search & Answer",
                description="Search knowledge base and provide detailed answers",
                tags=["search", "qa", "knowledge"],
                examples=["What is machine learning?", "Explain quantum computing concepts"],
                input_modes=["text/plain"],
                output_modes=["text/plain"],
            ),
        ]

    return AgentCard(
        name=agent_def.get("name") or settings.agent_name,
        description=agent_def.get("description") or settings.agent_description,
        url=settings.agent_url,
        version=raw_version,
        protocol_version="0.3.0",
        preferred_transport="HTTP+JSON",
        default_input_modes=agent_def.get("defaultInputModes", ["text/plain"]),
        default_output_modes=agent_def.get("defaultOutputModes", ["text/plain"]),
        capabilities=AgentCapabilities(
            streaming=capabilities_cfg.get("streaming", settings.streaming_enabled),
            push_notifications=capabilities_cfg.get("push_notifications", False),
        ),
        skills=skills,
        supports_authenticated_extended_card=False,
        provider=AgentProvider(
            organization=provider_cfg.get("organization", "CAMS"),
            url=provider_cfg.get("url", ""),
        ),
        documentation_url=None,
        icon_url=None,
    )


async def main():
    """Main entry point for the agent server."""
    Otel_Client.initialize_otel_client(
        service_name=settings.agent_name,
        environment=os.getenv("ENVIRONMENT", os.getenv("ENV", "dev")),
        agent_id=_read_agent_config_field("instance_id", default="N/A"),
    )

    RequestsInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()

    logger.info(f"Starting agent: {settings.agent_name} on {settings.host}:{settings.port}")

    agent_card = create_agent_card()
    executor = AgentExecutor()

    # Create OCR database tables if PostgreSQL is configured
    if settings.postgres_connection_string:
        try:
            from src.ocr.storage.database import create_tables
            await create_tables()
        except Exception as _db_err:
            logger.warning(f"OCR table creation skipped: {_db_err}")

    task_store = InMemoryTaskStore()
    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=task_store,
    )

    a2a_app = A2AFastAPIApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )

    app = a2a_app.build()

    FastAPIInstrumentor().instrument_app(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://aifabric-frontend.dev.cams.covasant.io",
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:8000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
            "http://127.0.0.1:8000",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if RATE_LIMITING_AVAILABLE and settings.rate_limit_enabled:
        rate_limiter = get_rate_limiter()
        app.add_middleware(
            RateLimitMiddleware,
            rate_limiter=rate_limiter,
            enabled=settings.rate_limit_enabled,
        )
        logger.info(f"Rate limiting enabled: {settings.rate_limit_per_minute}/min, {settings.rate_limit_per_hour}/hr")

    app.add_middleware(OtelContextMiddleware)

    health_checker = get_health_checker()

    @app.get("/health")
    async def health_check():
        health_status = await health_checker.get_health_status()
        status_code = 503 if health_status["status"] == "unhealthy" else 200
        from fastapi import Response
        return Response(
            content=json.dumps(health_status),
            status_code=status_code,
            media_type="application/json",
        )

    @app.get("/health/ready")
    async def readiness_check():
        is_ready = await health_checker.is_ready()
        if is_ready:
            return {"status": "ready"}
        from fastapi import Response
        return Response(
            content='{"status": "not ready"}',
            status_code=503,
            media_type="application/json",
        )

    @app.get("/health/live")
    async def liveness_check():
        is_alive = await health_checker.is_alive()
        if is_alive:
            return {"status": "alive"}
        from fastapi import Response
        return Response(
            content='{"status": "not alive"}',
            status_code=503,
            media_type="application/json",
        )

    if RATE_LIMITING_AVAILABLE:
        @app.get("/stats/rate-limits")
        async def rate_limit_stats():
            if not settings.rate_limit_enabled:
                return {"enabled": False}
            rate_limiter = get_rate_limiter()
            stats = rate_limiter.get_all_stats()
            return {
                "enabled": True,
                "config": {
                    "per_minute": settings.rate_limit_per_minute,
                    "per_hour": settings.rate_limit_per_hour,
                    "burst_size": settings.rate_limit_burst_size,
                },
                "tenants": stats,
            }

    if METRICS_AVAILABLE:
        @app.get("/metrics")
        async def metrics():
            from fastapi import Response
            metrics_data = metrics_collector.generate_metrics()
            content_type = metrics_collector.get_content_type()
            return Response(content=metrics_data, media_type=content_type)

    @app.post("/agent/run")
    async def agent_run_endpoint(http_request: Request, body: dict = Body(...)):
        """
        Direct agent execution endpoint — supports both the OCR Agent and the
        generic query agent.

        OCR request format (identified by the presence of "document"):
        {
            "document": "<s3-key or identifier>",
            "process_type": "individual_account_opening",
            "conversation_id": "optional-thread-id"
        }

        Generic query format (fallback):
        {
            "query": "Your question here",
            "conversation_id": "optional-conversation-id"
        }

        Response format:
        {
            "response": { ...OCRResponse... } | "<text answer>",
            "instance_id": "...",
            "conversation_id": "...",
            "user_id": "..."
        }

        HTTP status codes:
            200 — successful execution
            400 — invalid request (bad document, unknown process_type, missing query)
            500 — unexpected internal error
        """
        import uuid
        from fastapi.responses import JSONResponse
        from pydantic import ValidationError
        from src.ocr.models.ocr_request import OCRRequest

        # Read runtime context from config (injected at scaffold time from JWT)
        tenant_id = _read_agent_config_field("tenant_id", default="default")
        user_id = _read_agent_config_field("user_id", default="")
        instance_id = _read_agent_config_field("instance_id", default="N/A")

        thread_id = body.get("conversation_id") or f"thread_{uuid.uuid4().hex[:16]}"

        # ── OCR path — detected by presence of "document" field ──────────────
        if "document" in body:
            # Step 1: validate the request before touching any AWS service
            try:
                ocr_request = OCRRequest(
                    document=body.get("document", ""),
                    process_type=body.get("process_type", ""),
                    conversation_id=thread_id,
                )
            except ValidationError as exc:
                errors = [
                    {"field": e["loc"][-1], "message": e["msg"]}
                    for e in exc.errors()
                ]
                logger.warning(f"OCR request validation failed: {errors}")
                return JSONResponse(
                    status_code=400,
                    content={"error": "Invalid OCR request", "details": errors},
                )

            logger.info(
                f"OCR request received — process_type={ocr_request.process_type!r}, "
                f"conversation_id={thread_id}"
            )

            # Step 2: execute the graph
            try:
                ocr_response = await executor._run_ocr_graph(
                    ocr_request, tenant_id, thread_id
                )
            except Exception as exc:
                logger.error(f"OCR graph error: {type(exc).__name__}: {exc}")
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": "OCR processing failed",
                        "detail": str(exc),
                        "conversation_id": thread_id,
                    },
                )

            # Step 3: validate and return the response
            logger.info(
                f"OCR response returned — success={ocr_response.success}, "
                f"conversation_id={thread_id}"
            )

            return JSONResponse(
                status_code=200,
                content={
                    "response": ocr_response.model_dump(),
                    "instance_id": instance_id,
                    "conversation_id": thread_id,
                    "user_id": user_id,
                },
            )

        # ── Generic query path (original behaviour) ───────────────────────────
        try:
            from langchain_core.messages import HumanMessage

            query = body.get("query", "")
            if not query or not query.strip():
                return JSONResponse(
                    status_code=400,
                    content={"error": "Either 'document' (OCR request) or 'query' is required"},
                )

            logger.info(
                f"Agent request received — query_length={len(query)}, "
                f"conversation_id={thread_id}"
            )

            trace_id = uuid.uuid4().hex
            parent_span_id = uuid.uuid4().hex[:16]

            initial_state = {
                "messages": [HumanMessage(content=query)],
                "search_query": "",
                "retrieved_context": "",
                "final_response": "",
                "tenant_id": tenant_id,
                "thread_id": thread_id,
                "needs_retrieval": True,
                "_langfuse_trace_id": trace_id,
                "_langfuse_span_id": parent_span_id,
                "litellm_headers": None,
            }

            final_state = await executor._run_graph(initial_state, tenant_id, thread_id)
            response_text = final_state.get("final_response", "No response generated")

            logger.info(
                f"Agent response generated — response_length={len(response_text)}, "
                f"conversation_id={thread_id}"
            )

            return JSONResponse(
                status_code=200,
                content={
                    "response": response_text,
                    "instance_id": instance_id,
                    "conversation_id": thread_id,
                    "user_id": user_id,
                },
            )

        except Exception as exc:
            logger.error(f"Agent error: {type(exc).__name__}: {exc}")
            return JSONResponse(
                status_code=500,
                content={"error": "Agent processing failed", "detail": str(exc)},
            )

    config = uvicorn.Config(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )

    server = uvicorn.Server(config)
    logger.info(f"Agent ready at http://{settings.host}:{settings.port}")

    try:
        await server.serve()
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully")


if __name__ == "__main__":
    import platform
    if platform.system() == "Windows":
        # psycopg (and other async libs) are incompatible with Windows ProactorEventLoop.
        # SelectorEventLoop works on all platforms and is required for psycopg async.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Agent stopped by user")
        sys.exit(0)
