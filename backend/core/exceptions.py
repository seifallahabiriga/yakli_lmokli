from typing import Any


# =============================================================================
# Base
# =============================================================================

class ObservatoryException(Exception):
    """
    Root exception for all application-level errors.

    Every custom exception inherits from this, making it easy to catch
    anything the app raises without catching generic Python exceptions.
    """

    def __init__(
        self,
        message: str = "An unexpected error occurred.",
        status_code: int = 500,
        detail: Any = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"status_code={self.status_code}, "
            f"detail={self.detail!r})"
        )


# =============================================================================
# HTTP — mapped to FastAPI exception handlers in main.py
# =============================================================================

class BadRequestError(ObservatoryException):
    """400 — malformed input, invalid query parameters."""
    def __init__(self, message: str = "Bad request.", detail: Any = None) -> None:
        super().__init__(message=message, status_code=400, detail=detail)


class UnauthorizedError(ObservatoryException):
    """401 — missing or invalid authentication credentials."""
    def __init__(self, message: str = "Not authenticated.", detail: Any = None) -> None:
        super().__init__(message=message, status_code=401, detail=detail)


class ForbiddenError(ObservatoryException):
    """403 — authenticated but not allowed to access this resource."""
    def __init__(self, message: str = "Access forbidden.", detail: Any = None) -> None:
        super().__init__(message=message, status_code=403, detail=detail)


class NotFoundError(ObservatoryException):
    """404 — resource does not exist."""
    def __init__(self, message: str = "Resource not found.", detail: Any = None) -> None:
        super().__init__(message=message, status_code=404, detail=detail)


class ConflictError(ObservatoryException):
    """409 — resource already exists (e.g. duplicate email on registration)."""
    def __init__(self, message: str = "Resource conflict.", detail: Any = None) -> None:
        super().__init__(message=message, status_code=409, detail=detail)


class UnprocessableError(ObservatoryException):
    """422 — input is well-formed but semantically invalid."""
    def __init__(self, message: str = "Unprocessable entity.", detail: Any = None) -> None:
        super().__init__(message=message, status_code=422, detail=detail)


class RateLimitError(ObservatoryException):
    """429 — too many requests from this client."""
    def __init__(self, message: str = "Rate limit exceeded.", detail: Any = None) -> None:
        super().__init__(message=message, status_code=429, detail=detail)


class InternalError(ObservatoryException):
    """500 — unhandled server-side failure."""
    def __init__(self, message: str = "Internal server error.", detail: Any = None) -> None:
        super().__init__(message=message, status_code=500, detail=detail)


class ServiceUnavailableError(ObservatoryException):
    """503 — a downstream dependency (DB, Redis, LLM) is unreachable."""
    def __init__(self, message: str = "Service unavailable.", detail: Any = None) -> None:
        super().__init__(message=message, status_code=503, detail=detail)


# =============================================================================
# Auth
# =============================================================================

class TokenExpiredError(UnauthorizedError):
    def __init__(self) -> None:
        super().__init__(message="Token has expired.")


class TokenInvalidError(UnauthorizedError):
    def __init__(self) -> None:
        super().__init__(message="Token is invalid.")


class InvalidCredentialsError(UnauthorizedError):
    def __init__(self) -> None:
        super().__init__(message="Invalid email or password.")


class InsufficientPermissionsError(ForbiddenError):
    def __init__(self, required_role: str = "") -> None:
        msg = (
            f"Requires '{required_role}' role."
            if required_role
            else "Insufficient permissions."
        )
        super().__init__(message=msg)


# =============================================================================
# Domain — resource-specific
# =============================================================================

class UserNotFoundError(NotFoundError):
    def __init__(self, user_id: int | str) -> None:
        super().__init__(message=f"User '{user_id}' not found.")


class UserAlreadyExistsError(ConflictError):
    def __init__(self, email: str) -> None:
        super().__init__(message=f"User with email '{email}' already exists.")


class OpportunityNotFoundError(NotFoundError):
    def __init__(self, opportunity_id: int) -> None:
        super().__init__(message=f"Opportunity '{opportunity_id}' not found.")


class ClusterNotFoundError(NotFoundError):
    def __init__(self, cluster_id: int) -> None:
        super().__init__(message=f"Cluster '{cluster_id}' not found.")


class RecommendationNotFoundError(NotFoundError):
    def __init__(self, recommendation_id: int) -> None:
        super().__init__(message=f"Recommendation '{recommendation_id}' not found.")


# =============================================================================
# Scraping
# =============================================================================

class ScraperError(ObservatoryException):
    """Base for all scraper failures."""
    def __init__(self, message: str = "Scraper error.", detail: Any = None) -> None:
        super().__init__(message=message, status_code=500, detail=detail)


class ScraperTimeoutError(ScraperError):
    def __init__(self, url: str) -> None:
        super().__init__(message=f"Scraper timed out on '{url}'.", detail={"url": url})


class ScraperRateLimitedError(ScraperError):
    def __init__(self, url: str) -> None:
        super().__init__(
            message=f"Scraper was rate-limited by '{url}'.",
            detail={"url": url},
        )


class ScraperParseError(ScraperError):
    def __init__(self, url: str, reason: str = "") -> None:
        super().__init__(
            message=f"Failed to parse response from '{url}'. {reason}".strip(),
            detail={"url": url, "reason": reason},
        )


# =============================================================================
# ML / LLM
# =============================================================================

class MLError(ObservatoryException):
    """Base for all ML pipeline failures."""
    def __init__(self, message: str = "ML pipeline error.", detail: Any = None) -> None:
        super().__init__(message=message, status_code=500, detail=detail)


class LLMProviderError(MLError):
    def __init__(self, provider: str, reason: str = "") -> None:
        super().__init__(
            message=f"LLM provider '{provider}' failed. {reason}".strip(),
            detail={"provider": provider, "reason": reason},
        )


class LLMAllProvidersFailedError(MLError):
    def __init__(self) -> None:
        super().__init__(message="All LLM providers failed. No fallback available.")


class EmbeddingError(MLError):
    def __init__(self, reason: str = "") -> None:
        super().__init__(message=f"Embedding generation failed. {reason}".strip())


class ClusteringError(MLError):
    def __init__(self, reason: str = "") -> None:
        super().__init__(message=f"Clustering failed. {reason}".strip())


# =============================================================================
# Infrastructure
# =============================================================================

class DatabaseError(ObservatoryException):
    def __init__(self, reason: str = "") -> None:
        super().__init__(
            message=f"Database operation failed. {reason}".strip(),
            status_code=500,
        )


class CacheError(ObservatoryException):
    def __init__(self, reason: str = "") -> None:
        super().__init__(
            message=f"Cache operation failed. {reason}".strip(),
            status_code=500,
        )


class TaskQueueError(ObservatoryException):
    def __init__(self, reason: str = "") -> None:
        super().__init__(
            message=f"Task queue error. {reason}".strip(),
            status_code=500,
        )