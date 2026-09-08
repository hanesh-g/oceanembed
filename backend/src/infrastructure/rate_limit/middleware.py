from collections.abc import Callable
from typing import cast

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from ...modules.common.utils.logger import get_logger
from ..config import get_settings
from .exceptions import RateLimitException
from .provider import increment_and_check
from .utils import sanitize_path

logger = get_logger(__name__)

settings = get_settings()
DEFAULT_LIMIT = settings.DEFAULT_RATE_LIMIT_LIMIT
DEFAULT_PERIOD = settings.DEFAULT_RATE_LIMIT_PERIOD


async def _check_rate_limit(request: Request) -> None:
    """Internal implementation of check_rate_limit without FastAPI dependency injection."""
    if not settings.RATE_LIMITER_ENABLED:
        return

    if hasattr(request.app.state, "initialization_complete"):
        await request.app.state.initialization_complete.wait()

    original_path = request.url.path
    sanitized_path = sanitize_path(original_path)

    user_id = request.client.host if request.client and hasattr(request.client, "host") else "unknown"
    limit, period = DEFAULT_LIMIT, DEFAULT_PERIOD

    key = f"ratelimit:{user_id}:{sanitized_path}"

    try:
        count, is_limited = await increment_and_check(
            key=key, limit=limit, period=period, fail_open=settings.RATE_LIMITER_FAIL_OPEN
        )

        request.state.rate_limit_headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(max(0, limit - count)),
            "X-RateLimit-Reset": str(period),
        }

        if is_limited:
            logger.warning(f"Rate limit exceeded for {user_id} on path {sanitized_path}. Count: {count}, Limit: {limit}")
            raise RateLimitException(f"Rate limit exceeded. Try again in {period} seconds.")

    except RateLimitException:
        raise
    except Exception as e:
        logger.error(f"Error checking rate limit for {user_id} on path {sanitized_path}: {e}")
        if not settings.RATE_LIMITER_FAIL_OPEN:
            logger.warning("Blocking request due to fail-closed policy")
            raise RateLimitException("Error checking rate limit. Access denied as a precaution.")


async def check_rate_limit(request: Request) -> None:
    """Check if the current request exceeds rate limits.

    Args:
        request: The current request.

    Raises:
        RateLimitException: If the rate limit is exceeded.
    """
    await _check_rate_limit(request)


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Middleware for applying rate limits to all requests."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process a request through the middleware."""
        response = await call_next(request)

        if hasattr(request.state, "rate_limit_headers"):
            for key, value in request.state.rate_limit_headers.items():
                response.headers[key] = value

        return cast(Response, response)
