"""Custom exceptions for Japanese transit search."""


class TransitSearchError(Exception):
    """Base exception for transit search errors."""

    pass


class StationNotFoundError(TransitSearchError):
    """Raised when a station name cannot be found."""

    pass


class RouteNotFoundError(TransitSearchError):
    """Raised when no route can be found between stations."""

    pass


class ScrapingError(TransitSearchError):
    """Raised when there's an error scraping data from the website."""

    pass


class NetworkError(TransitSearchError):
    """Raised when there's a network-related error."""

    pass


class ValidationError(TransitSearchError):
    """Raised when input validation fails."""

    pass
