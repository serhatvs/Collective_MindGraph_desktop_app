"""Shared OpenAPI error declarations for the versioned API."""

from .system_schemas import ErrorResponse

ERROR_RESPONSES = {
    404: {"model": ErrorResponse, "description": "Resource not found."},
    409: {"model": ErrorResponse, "description": "State conflict."},
    422: {"model": ErrorResponse, "description": "Invalid request."},
    500: {"model": ErrorResponse, "description": "Unexpected engine failure."},
    503: {"model": ErrorResponse, "description": "Local provider unavailable."},
}
