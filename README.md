# BeNeat Cleaner Finder

Finds the best-rated BeNeat housekeeper for any district served by the
[BeNeat](https://beneat.co) platform, ranking by a weighted score of completed
jobs and repeat booking rate.

## How it works

1. Loads province/district/service reference data from BeNeat's public API
   (cached locally for 30 days by default).
2. Prompts you to pick a province, then a district.
3. Paginates BeNeat's cleaner listing for that district (general cleaning
   service only).
4. Keeps only cleaners who hold the **Excellent Provider** badge
   (`is_excellent`) and have a positive repeat booking rate.
5. Ranks them by `0.4 × rank(jobs) + 0.6 × rank(repeat-rate)`; ties broken by
   raw job count.
6. Writes the ranked table to `RESULTS.md` and prints the top 3.

## Prerequisites

- **Python**: 3.12+
- **uv**: (Recommended) Fast Python package installer and resolver.

## Installation

```bash
make setup
```

If using standard pip:

```bash
pip install -e ".[dev]"
```

## Usage

```bash
make run
```

Options:

- `--refresh` — ignore the local cache and re-fetch province/district data.
- `--service N` — filter by a different service ID (default `1`, general cleaning).
- `--workers N` — concurrency for fetching repeat rates (default `8`).

Example:

```bash
PYTHONPATH=src uv run python -m beneat.main --refresh --workers 16
```

## Development

```bash
make lint    # ruff + mypy
make format  # ruff format
make test    # pytest with coverage
```

## Configuration

Settings are read from `.env` (see `.env.example`) or environment variables:

- `BENEAT_API_BASE` — default `https://lumen.beneat.co`
- `CACHE_TTL_DAYS` — default `30`
- `SERVICE_ID` — default `1`
- `CACHE_DIR` — default `~/.cache/beneat`

## License

MIT
