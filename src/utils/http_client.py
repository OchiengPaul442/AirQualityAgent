"""
HTTP Client Utilities with Retry Logic and Timeout Handling

Provides resilient HTTP requests with:
- Automatic retries on transient failures
- Configurable timeouts
- User-friendly error messages
- Connection pooling
"""

import logging
from typing import Any, Dict, Optional

import httpx
from tenacity import (  # type: ignore[import-untyped]
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


class HTTPClientError(Exception):
    """Base exception for HTTP client errors"""

    pass


class TimeoutError(HTTPClientError):
    """Request timeout error"""

    pass


class NetworkError(HTTPClientError):
    """Network connectivity error"""

    pass


class ServiceUnavailableError(HTTPClientError):
    """External service unavailable"""

    pass


# Configure default timeout (connect, read, write, pool)
DEFAULT_TIMEOUT = httpx.Timeout(
    connect=10.0,  # Time to establish connection
    read=30.0,  # Time to read response
    write=10.0,  # Time to write request
    pool=5.0,  # Time to get connection from pool
)


# Retry configuration
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(
        (
            httpx.TimeoutException,
            httpx.ConnectError,
            httpx.ReadError,
            httpx.WriteError,
            httpx.PoolTimeout,
        )
    ),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def resilient_get(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    timeout: Optional[httpx.Timeout] = None,
) -> httpx.Response:
    """
    Perform a GET request with automatic retry logic.

    Args:
        url: Target URL
        headers: Request headers
        params: Query parameters
        timeout: Custom timeout configuration

    Returns:
        httpx.Response object

    Raises:
        TimeoutError: Request timed out after retries
        NetworkError: Network connectivity issues
        ServiceUnavailableError: External service unavailable
        HTTPClientError: Other HTTP errors
    """
    try:
        async with httpx.AsyncClient(timeout=timeout or DEFAULT_TIMEOUT) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response

    except httpx.PoolTimeout as e:
        logger.error(f"Connection pool timeout for {url}: {e}")
        raise TimeoutError(
            f"Too many concurrent requests. Please wait a moment and try again."
        ) from e

    except httpx.TimeoutException as e:
        logger.error(f"Request timeout for {url}: {e}")
        raise TimeoutError(
            f"The request timed out. The service may be slow or unresponsive. Please try again later."
        ) from e

    except (httpx.ConnectError, httpx.ReadError, httpx.WriteError) as e:
        logger.error(f"Network error for {url}: {e}")
        raise NetworkError(
            f"Unable to connect to the service. Please check your internet connection and try again."
        ) from e

    except httpx.HTTPStatusError as e:
        if e.response.status_code >= 500:
            logger.error(f"Server error for {url}: {e.response.status_code}")
            raise ServiceUnavailableError(
                f"The external service is currently unavailable (status {e.response.status_code}). Please try again later."
            ) from e
        else:
            logger.error(f"HTTP error for {url}: {e.response.status_code}")
            raise HTTPClientError(
                f"Request failed with status {e.response.status_code}: {e.response.text[:200]}"
            ) from e

    except Exception as e:
        logger.error(f"Unexpected error for {url}: {e}")
        raise HTTPClientError(f"An unexpected error occurred while contacting the service.") from e


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(
        (
            httpx.TimeoutException,
            httpx.ConnectError,
            httpx.ReadError,
            httpx.WriteError,
            httpx.PoolTimeout,
        )
    ),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def resilient_post(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    json: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
    timeout: Optional[httpx.Timeout] = None,
) -> httpx.Response:
    """
    Perform a POST request with automatic retry logic.

    Args:
        url: Target URL
        headers: Request headers
        json: JSON payload
        data: Form data payload
        timeout: Custom timeout configuration

    Returns:
        httpx.Response object

    Raises:
        TimeoutError: Request timed out after retries
        NetworkError: Network connectivity issues
        ServiceUnavailableError: External service unavailable
        HTTPClientError: Other HTTP errors
    """
    try:
        async with httpx.AsyncClient(timeout=timeout or DEFAULT_TIMEOUT) as client:
            response = await client.post(url, headers=headers, json=json, data=data)
            response.raise_for_status()
            return response

    except httpx.PoolTimeout as e:
        logger.error(f"Connection pool timeout for {url}: {e}")
        raise TimeoutError(
            f"Too many concurrent requests. Please wait a moment and try again."
        ) from e

    except httpx.TimeoutException as e:
        logger.error(f"Request timeout for {url}: {e}")
        raise TimeoutError(
            f"The request timed out. The service may be slow or unresponsive. Please try again later."
        ) from e

    except (httpx.ConnectError, httpx.ReadError, httpx.WriteError) as e:
        logger.error(f"Network error for {url}: {e}")
        raise NetworkError(
            f"Unable to connect to the service. Please check your internet connection and try again."
        ) from e

    except httpx.HTTPStatusError as e:
        if e.response.status_code >= 500:
            logger.error(f"Server error for {url}: {e.response.status_code}")
            raise ServiceUnavailableError(
                f"The external service is currently unavailable (status {e.response.status_code}). Please try again later."
            ) from e
        else:
            logger.error(f"HTTP error for {url}: {e.response.status_code}")
            raise HTTPClientError(
                f"Request failed with status {e.response.status_code}: {e.response.text[:200]}"
            ) from e

    except Exception as e:
        logger.error(f"Unexpected error for {url}: {e}")
        raise HTTPClientError(f"An unexpected error occurred while contacting the service.") from e


def create_client(timeout: Optional[httpx.Timeout] = None) -> httpx.AsyncClient:
    """
    Create a configured async HTTP client with connection pooling.

    Args:
        timeout: Custom timeout configuration

    Returns:
        Configured httpx.AsyncClient
    """
    return httpx.AsyncClient(
        timeout=timeout or DEFAULT_TIMEOUT,
        limits=httpx.Limits(
            max_connections=100, max_keepalive_connections=20, keepalive_expiry=30.0
        ),
        follow_redirects=True,
    )
