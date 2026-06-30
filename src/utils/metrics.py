"""
Prometheus metrics collection and exposition.
Tracks requests, latency, errors, LLM usage, and node execution metrics.
"""

from typing import Optional, Callable
from functools import wraps
import time
from contextlib import contextmanager

from cams_otel_lib import Logger as logger, otel_trace

# Track if Prometheus is available
_prometheus_available = False

try:
    from prometheus_client import (
        Counter,
        Histogram,
        Gauge,
        generate_latest,
        CollectorRegistry,
        CONTENT_TYPE_LATEST,
    )

    _prometheus_available = True
except ImportError:
    logger.debug("Prometheus client not installed - metrics disabled")


class MetricsCollector:
    """
    Prometheus metrics collector for agent monitoring.

    Tracks:
    - Request count and rate
    - Request duration and latency
    - Error rate
    - LLM token usage and costs
    - Node execution time
    - Active requests

    Example:
        >>> collector = get_metrics_collector()
        >>> collector.track_request("POST", "/", 200, 0.5, "acme_corp")
        >>> collector.track_llm_tokens("openai", "gpt-4o", 100, 50, 0.002)
    """

    def __init__(self, enabled: bool = True):
        """
        Initialize metrics collector.

        Args:
            enabled: Enable/disable metrics collection
        """
        self.enabled = enabled and _prometheus_available

        if not self.enabled:
            if not _prometheus_available:
                logger.info("Metrics disabled - prometheus-client not installed")
            else:
                logger.info("Metrics disabled by configuration")
            return

        # Registry for metrics
        self.registry = CollectorRegistry()

        # Request metrics
        self.requests_total = Counter(
            "agent_requests_total",
            "Total number of requests",
            ["method", "endpoint", "status", "tenant_id"],
            registry=self.registry,
        )

        self.request_duration = Histogram(
            "agent_request_duration_seconds",
            "Request duration in seconds",
            ["method", "endpoint", "tenant_id"],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
            registry=self.registry,
        )

        self.requests_in_progress = Gauge(
            "agent_requests_in_progress",
            "Number of requests currently being processed",
            ["method", "endpoint"],
            registry=self.registry,
        )

        # Error metrics
        self.errors_total = Counter(
            "agent_errors_total",
            "Total number of errors",
            ["error_type", "tenant_id"],
            registry=self.registry,
        )

        # LLM metrics
        self.llm_tokens_total = Counter(
            "agent_llm_tokens_total",
            "Total LLM tokens used",
            ["provider", "model", "type", "tenant_id"],
            registry=self.registry,
        )

        self.llm_cost_total = Counter(
            "agent_llm_cost_usd_total",
            "Total LLM cost in USD",
            ["provider", "model", "tenant_id"],
            registry=self.registry,
        )

        self.llm_requests_total = Counter(
            "agent_llm_requests_total",
            "Total LLM requests",
            ["provider", "model", "tenant_id"],
            registry=self.registry,
        )

        self.llm_duration = Histogram(
            "agent_llm_duration_seconds",
            "LLM request duration in seconds",
            ["provider", "model"],
            buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
            registry=self.registry,
        )

        # Node execution metrics
        self.node_executions_total = Counter(
            "agent_node_executions_total",
            "Total node executions",
            ["node_name", "status", "tenant_id"],
            registry=self.registry,
        )

        self.node_duration = Histogram(
            "agent_node_duration_seconds",
            "Node execution duration in seconds",
            ["node_name"],
            buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
            registry=self.registry,
        )

        # Tool metrics
        self.tool_invocations_total = Counter(
            "agent_tool_invocations_total",
            "Total tool invocations",
            ["tool_name", "status", "tenant_id"],
            registry=self.registry,
        )

        self.tool_duration = Histogram(
            "agent_tool_duration_seconds",
            "Tool execution duration in seconds",
            ["tool_name"],
            buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0),
            registry=self.registry,
        )

        logger.info("Prometheus metrics collector initialized")

    @otel_trace
    def track_request(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration: float,
        tenant_id: str = "default",
    ):
        """
        Track HTTP request metrics.

        Args:
            method: HTTP method
            endpoint: Request endpoint
            status_code: Response status code
            duration: Request duration in seconds
            tenant_id: Tenant identifier
        """
        if not self.enabled:
            return

        try:
            self.requests_total.labels(
                method=method,
                endpoint=endpoint,
                status=str(status_code),
                tenant_id=tenant_id,
            ).inc()

            self.request_duration.labels(
                method=method, endpoint=endpoint, tenant_id=tenant_id
            ).observe(duration)

        except Exception as e:
            logger.debug(f"Failed to track request metrics: {e}")

    @contextmanager
    def track_request_in_progress(self, method: str, endpoint: str):
        """
        Context manager to track requests in progress.

        Args:
            method: HTTP method
            endpoint: Request endpoint
        """
        if not self.enabled:
            yield
            return

        try:
            self.requests_in_progress.labels(method=method, endpoint=endpoint).inc()
            yield
        finally:
            try:
                self.requests_in_progress.labels(method=method, endpoint=endpoint).dec()
            except Exception as e:
                logger.debug(f"Failed to track request in progress: {e}")

    @otel_trace
    def track_error(self, error_type: str, tenant_id: str = "default"):
        """
        Track error occurrence.

        Args:
            error_type: Type of error (e.g., ValueError, TimeoutError)
            tenant_id: Tenant identifier
        """
        if not self.enabled:
            return

        try:
            self.errors_total.labels(error_type=error_type, tenant_id=tenant_id).inc()
        except Exception as e:
            logger.debug(f"Failed to track error metrics: {e}")

    @otel_trace
    def track_llm_tokens(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        tenant_id: str = "default",
    ):
        """
        Track LLM token usage and cost.

        Args:
            provider: LLM provider (openai, anthropic, google)
            model: Model name
            input_tokens: Input tokens used
            output_tokens: Output tokens used
            cost: Cost in USD
            tenant_id: Tenant identifier
        """
        if not self.enabled:
            return

        try:
            self.llm_tokens_total.labels(
                provider=provider, model=model, type="input", tenant_id=tenant_id
            ).inc(input_tokens)

            self.llm_tokens_total.labels(
                provider=provider, model=model, type="output", tenant_id=tenant_id
            ).inc(output_tokens)

            self.llm_cost_total.labels(
                provider=provider, model=model, tenant_id=tenant_id
            ).inc(cost)

            self.llm_requests_total.labels(
                provider=provider, model=model, tenant_id=tenant_id
            ).inc()

        except Exception as e:
            logger.debug(f"Failed to track LLM token metrics: {e}")

    @otel_trace
    def track_llm_duration(self, provider: str, model: str, duration: float):
        """
        Track LLM request duration.

        Args:
            provider: LLM provider
            model: Model name
            duration: Duration in seconds
        """
        if not self.enabled:
            return

        try:
            self.llm_duration.labels(provider=provider, model=model).observe(duration)
        except Exception as e:
            logger.debug(f"Failed to track LLM duration: {e}")

    @otel_trace
    def track_node_execution(
        self,
        node_name: str,
        duration: float,
        status: str = "success",
        tenant_id: str = "default",
    ):
        """
        Track node execution metrics.

        Args:
            node_name: Name of the node
            duration: Execution duration in seconds
            status: Execution status (success, error)
            tenant_id: Tenant identifier
        """
        if not self.enabled:
            return

        try:
            self.node_executions_total.labels(
                node_name=node_name, status=status, tenant_id=tenant_id
            ).inc()

            self.node_duration.labels(node_name=node_name).observe(duration)

        except Exception as e:
            logger.debug(f"Failed to track node execution metrics: {e}")

    @otel_trace
    def track_tool_invocation(
        self,
        tool_name: str,
        duration: float,
        status: str = "success",
        tenant_id: str = "default",
    ):
        """
        Track tool invocation metrics.

        Args:
            tool_name: Name of the tool
            duration: Execution duration in seconds
            status: Execution status (success, error)
            tenant_id: Tenant identifier
        """
        if not self.enabled:
            return

        try:
            self.tool_invocations_total.labels(
                tool_name=tool_name, status=status, tenant_id=tenant_id
            ).inc()

            self.tool_duration.labels(tool_name=tool_name).observe(duration)

        except Exception as e:
            logger.debug(f"Failed to track tool invocation metrics: {e}")

    @otel_trace
    def generate_metrics(self) -> bytes:
        """
        Generate Prometheus metrics in text format.

        Returns:
            Metrics in Prometheus text format
        """
        if not self.enabled:
            return b"# Metrics disabled\n"

        try:
            return generate_latest(self.registry)
        except Exception as e:
            logger.error(f"Failed to generate metrics: {e}")
            return b"# Error generating metrics\n"

    @otel_trace
    def get_content_type(self) -> str:
        """
        Get Prometheus metrics content type.

        Returns:
            Content type string
        """
        if not self.enabled:
            return "text/plain"
        return CONTENT_TYPE_LATEST


def track_request_metrics(func: Callable) -> Callable:
    """
    Decorator to automatically track request metrics.

    Usage:
        @track_request_metrics
        async def my_endpoint():
            ...
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        collector = get_metrics_collector()

        # Extract request info (works with FastAPI)
        request = kwargs.get("request") or (args[0] if args else None)

        start_time = time.time()
        status_code = 200

        try:
            result = await func(*args, **kwargs)
            return result
        except Exception as e:
            status_code = 500
            collector.track_error(type(e).__name__)
            raise
        finally:
            duration = time.time() - start_time

            if request and hasattr(request, "method"):
                method = request.method
                endpoint = request.url.path
                tenant_id = getattr(request.state, "claims", {}).get("tenant_uuid", "unknown")

                collector.track_request(
                    method, endpoint, status_code, duration, tenant_id
                )

    return wrapper


def track_node_metrics(node_name: str):
    """
    Decorator to automatically track node execution metrics.

    Usage:
        @track_node_metrics("query_processor")
        async def execute(self, state):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            collector = get_metrics_collector()

            # Extract tenant_id from state (populated from JWT claims by route handler)
            state = kwargs.get("state") or (args[1] if len(args) > 1 else {})
            tenant_id = (
                state.get("tenant_id", "unknown")
                if isinstance(state, dict)
                else "unknown"
            )

            start_time = time.time()
            status = "success"

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                collector.track_error(type(e).__name__, tenant_id)
                raise
            finally:
                duration = time.time() - start_time
                collector.track_node_execution(node_name, duration, status, tenant_id)

        return wrapper

    return decorator


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


@otel_trace
def get_metrics_collector() -> MetricsCollector:
    """
    Get global metrics collector instance.

    Returns:
        MetricsCollector instance
    """
    global _metrics_collector

    if _metrics_collector is None:
        from src.config.settings import settings

        enabled = getattr(settings, "metrics_enabled", True)
        _metrics_collector = MetricsCollector(enabled=enabled)

    return _metrics_collector
