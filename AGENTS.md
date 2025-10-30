# Agent Development Guide

## Commands
- **Tests**: `uv run pytest` (all), `uv run pytest tests/unit/test_models.py::test_station_creation` (single test)
- **Lint**: `uv run ruff check src/` (linting), `uv run ruff format src/` (formatting) 
- **Type check**: `uv run mypy src/jp_transit_search/`
- **Coverage**: `uv run pytest --cov=jp_transit_search --cov-report=html`
- **Install deps**: `uv sync` (development), `uv sync --no-dev` (production only)

## Code Style
- **Formatting**: Black (88 char line length), Ruff for imports/linting
- **Types**: Full type hints required (`mypy --strict`), use `Optional[]` explicitly
- **Imports**: Standard library first, then third-party, then local (sorted by ruff)
- **Naming**: snake_case for functions/variables, PascalCase for classes, UPPER_CASE for constants
- **Docstrings**: Triple quotes, one-line summary + detailed description for complex functions
- **Error handling**: Custom exceptions in `core/exceptions.py`, inherit from `TransitSearchError`

## Project Structure
- **Models**: Pydantic models in `core/models.py` with Field descriptions
- **CLI**: Click commands in `cli/`, use Rich console for output formatting
- **Core logic**: Business logic in `core/`, separate scraping from data models
- **Tests**: Pytest with fixtures in `conftest.py`, mark slow tests with `@pytest.mark.slow`
- **Entry points**: CLI via `jp-transit`, MCP server via `jp-transit-mcp`