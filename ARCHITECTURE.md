# System Architecture

## Overview
A modular, single-entrypoint CLI tool designed for reliability, strict type safety, and clean configuration.

## Component Map
- **[main.py](file:///beneats/boilerplate/src/beneat/main.py)**: The entry point for execution. Coordinates initialization and application logic.
- **[config.py](file:///beneats/boilerplate/src/beneat/config.py)**: The settings loading component. Utilizes `pydantic-settings` to load and validate configurations from environment variables or a `.env` file.
- **[tests/](file:///beneats/boilerplate/tests)**: Verification suite running on `pytest` to validate application behavior, with test coverage tracked via `pytest-cov`.

## Data Flow
1. **Bootstrap**: The application starts through the Makefile via the `make run` command, setting the proper pythonpath context.
2. **Configuration Loading**: [config.py](file:///beneats/boilerplate/src/beneat/config.py) loads settings from the environment, validating types.
3. **Execution**: [main.py](file:///beneats/boilerplate/src/beneat/main.py) receives configuration and executes CLI procedures.

## Key Design Decisions (ADRs)
- **Strict Linting & Mypy Checks**: Integrated `mypy` and expanded `ruff` checks to catch potential runtime type/style bugs during development.
- **Pydantic Validation**: Decoupled dotenv loading into a validated settings class to ensure invalid environment configurations fail early during bootstrapping.

## Security & Compliance
- Environment files (`.env`) must not be committed to Git. A `.env.example` file is provided to document configuration shapes.
