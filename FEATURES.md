# Selected Features

This agent template has been customized with the following features:

### Observability

**Langfuse Observability**
- Automatic tracing of all agent executions and LLM calls
- Real-time token usage and cost tracking per request
- Visual trace timeline with prompts, responses, and metadata

**Prometheus Metrics**
- Request, latency, error, and LLM usage metrics
- Histogram-based latency tracking (p50, p95, p99)
- Prometheus scraping endpoint at /metrics

**LiteLLM Gateway**
- Centralized LLM request routing through LiteLLM proxy
- Track all your API calls, costs, and usage in a native control tower
- Unified observability across multiple LLM providers (OpenAI, Anthropic, Google)
- Built-in caching, load balancing, and fallback support

### Production

**Rate Limiting**
- Per-tenant sliding window rate limits (60/min, 1000/hour)
- Burst capacity for handling traffic spikes
- Rate limit headers and stats endpoint at /stats/rate-limits

### Storage

**PostgreSQL Database**
- Persistent conversation memory across sessions
- LangGraph checkpoint storage for state persistence
- Automatic fallback to in-memory if not configured

## Core Features (Always Included)

- LangGraph Workflow Engine
- A2A Protocol Support
- Multi-LLM Provider Support (OpenAI, Anthropic, Google)
- Structured JSON Logging
- Health Check Endpoints
- Tool Auto-Discovery System
- LiteLLM Gateway Integration

---

**For detailed documentation, see:**
- `README.md` - Complete user guide with deployment workflow
- `docs/COMPLETE_GUIDE.md` - Deep technical documentation
