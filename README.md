# Housekeeping Finder

Finds the best-rated BeNeat housekeeper for any district served by the
[BeNeat](https://beneat.co) platform, ranking by a weighted score of completed
jobs and repeat booking rate.

## How it works

1. Loads province/district/service reference data from BeNeat's public API
   (cached locally for 30 days by default).
2. Prompts you to pick a province, then a district. Districts are ordered by
   English name and the redundant English `Khet` prefix is hidden.
3. Prompts for a booking date and an optional start time. Entered times are
   floored to the previous half hour between 07:00 and 19:30. Leaving the time
   blank finds the first available two-hour start before 14:00.
4. Paginates BeNeat's cleaner listing for that district (general cleaning
   service only).
5. Keeps only cleaners who hold the **Excellent Provider** badge
   (`is_excellent`) and have a positive repeat booking rate.
6. Checks BeNeat's live provider calendar and existing jobs for a two-hour,
   one-time cleaning, including the same between-job buffers used by the site.
7. Ranks available cleaners by `0.4 × rank(jobs) + 0.6 × rank(repeat-rate)`;
   ties are broken by
   raw job count.
8. Writes the ranked table to `output/RESULTS.html` and prints the top 3.
   Profile links in the HTML report open in a new tab.

The CLI displays live counters while it scans listings, fetches repeat rates,
and checks calendars.

## Prerequisites

- **Python**: 3.12+
- **uv**: (Recommended) Fast Python package installer and resolver.

The application uses portable Python APIs and is supported on Linux and macOS.
`uv` creates and manages the appropriate environment on either platform.

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
uv run main.py
```

You can also use `make run`.

Options:

- `--refresh` — ignore the local cache and re-fetch province/district data.
- `--workers N` — concurrency for fetching repeat rates (default `8`).

Example:

```bash
uv run main.py --refresh --workers 16
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
- `CACHE_DIR` — default `~/.cache/beneat`

## License

MIT
