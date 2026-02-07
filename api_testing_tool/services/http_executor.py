"""
HTTP execution service for sending HTTP requests.

This service handles the actual HTTP request execution using httpx,
including variable substitution, response capture, and error handling.
"""

import json
import time
from typing import Any

import httpx
from sqlalchemy.orm import Session

from ..models.environment import Environment
from ..schemas.execute import ExecuteRequest, ExecuteResponse, ExecuteErrorResponse
from .variable_substitution import substitute, substitute_dict


# Default timeout in seconds
DEFAULT_TIMEOUT = 30.0


def get_environment_variables(db: Session, environment_id: int | None) -> tuple[dict[str, str], str]:
    """
    Get variables and base_url from the specified environment or active environment.
    
    Args:
        db: Database session
        environment_id: Specific environment ID, or None to use active environment
        
    Returns:
        Tuple of (variable dict, base_url string)
    """
    if environment_id is not None:
        env = db.query(Environment).filter(Environment.id == environment_id).first()
    else:
        env = db.query(Environment).filter(Environment.is_active == True).first()
    
    if not env:
        return {}, ""
    
    return {var.key: var.value for var in env.variables}, env.base_url or ""


def apply_variable_substitution(
    request: ExecuteRequest,
    variables: dict[str, str]
) -> tuple[ExecuteRequest, list[str]]:
    """
    Apply variable substitution to all parts of a request.
    
    Args:
        request: The request to process
        variables: Variable name to value mapping
        
    Returns:
        Tuple of (processed request, list of warning messages)
    """
    warnings: list[str] = []
    
    # Substitute URL
    url, url_unmatched = substitute(request.url, variables)
    if url_unmatched:
        warnings.extend([f"Undefined variable in URL: {{{{{v}}}}}" for v in url_unmatched])
    
    # Substitute headers
    headers, headers_unmatched = substitute_dict(request.headers, variables)
    if headers_unmatched:
        warnings.extend([f"Undefined variable in headers: {{{{{v}}}}}" for v in headers_unmatched])
    
    # Substitute query params
    query_params, params_unmatched = substitute_dict(request.query_params, variables)
    if params_unmatched:
        warnings.extend([f"Undefined variable in query params: {{{{{v}}}}}" for v in params_unmatched])
    
    # Substitute body
    body = request.body
    if body:
        body, body_unmatched = substitute(body, variables)
        if body_unmatched:
            warnings.extend([f"Undefined variable in body: {{{{{v}}}}}" for v in body_unmatched])
    
    # Create new request with substituted values
    processed = ExecuteRequest(
        method=request.method,
        url=url,
        headers=headers,
        query_params=query_params,
        body_type=request.body_type,
        body=body
    )
    
    return processed, warnings


def parse_json_body(body: str | None, content_type: str | None) -> Any | None:
    """
    Try to parse response body as JSON if content type indicates JSON.
    
    Args:
        body: Response body string
        content_type: Content-Type header value
        
    Returns:
        Parsed JSON object or None if not JSON or parsing fails
    """
    if not body or not content_type:
        return None
    
    if "application/json" in content_type.lower():
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return None
    
    return None


async def execute_request(
    request: ExecuteRequest,
    db: Session | None = None,
    environment_id: int | None = None,
    timeout: float = DEFAULT_TIMEOUT
) -> ExecuteResponse | ExecuteErrorResponse:
    """
    Execute an HTTP request and return the response.
    
    Args:
        request: The request configuration to execute
        db: Database session for fetching environment variables
        environment_id: Specific environment ID, or None to use active environment
        timeout: Request timeout in seconds
        
    Returns:
        ExecuteResponse on success, ExecuteErrorResponse on failure
    """
    warnings: list[str] = []
    
    # Apply variable substitution if database session provided
    if db is not None:
        variables, base_url = get_environment_variables(db, environment_id)
        request, substitution_warnings = apply_variable_substitution(request, variables)
        warnings.extend(substitution_warnings)
        # Prepend base_url if the URL doesn't already start with http
        if base_url and not request.url.startswith(('http://', 'https://')):
            url = base_url.rstrip('/') + '/' + request.url.lstrip('/')
            request = ExecuteRequest(
                method=request.method,
                url=url,
                headers=request.headers,
                query_params=request.query_params,
                body_type=request.body_type,
                body=request.body
            )
    
    # Prepare request parameters
    headers = dict(request.headers)
    params = dict(request.query_params) if request.query_params else None
    
    # Prepare body based on body_type
    content: str | None = None
    data: dict[str, str] | None = None
    
    if request.body:
        if request.body_type == "json":
            content = request.body
            if "Content-Type" not in headers:
                headers["Content-Type"] = "application/json"
        elif request.body_type == "form":
            # Parse form data from body (expected format: key=value&key2=value2)
            try:
                data = dict(pair.split("=", 1) for pair in request.body.split("&") if "=" in pair)
            except ValueError:
                data = None
                content = request.body
        else:  # raw
            content = request.body
    
    # Execute the request
    try:
        start_time = time.perf_counter()
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method=request.method,
                url=request.url,
                headers=headers,
                params=params,
                content=content,
                data=data
            )
        
        end_time = time.perf_counter()
        response_time_ms = int((end_time - start_time) * 1000)
        
        # Get response body
        response_body = response.text
        response_size = len(response.content)
        
        # Convert headers to dict
        response_headers = dict(response.headers)
        
        # Try to parse JSON body
        content_type = response_headers.get("content-type", "")
        body_json = parse_json_body(response_body, content_type)
        
        return ExecuteResponse(
            status_code=response.status_code,
            status_text=response.reason_phrase or "",
            headers=response_headers,
            body=response_body,
            body_json=body_json,
            response_time_ms=response_time_ms,
            response_size=response_size,
            warnings=warnings
        )
        
    except httpx.TimeoutException:
        return ExecuteErrorResponse(
            error="Request timed out",
            error_type="timeout",
            details=f"Request exceeded {timeout} seconds timeout"
        )
    except httpx.ConnectError as e:
        return ExecuteErrorResponse(
            error="Failed to connect to server",
            error_type="network_error",
            details=str(e)
        )
    except httpx.InvalidURL as e:
        return ExecuteErrorResponse(
            error="Invalid URL",
            error_type="invalid_url",
            details=str(e)
        )
    except httpx.HTTPError as e:
        return ExecuteErrorResponse(
            error="HTTP error occurred",
            error_type="network_error",
            details=str(e)
        )
    except Exception as e:
        return ExecuteErrorResponse(
            error="An unexpected error occurred",
            error_type="unknown",
            details=str(e)
        )
