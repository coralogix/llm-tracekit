#!/bin/sh
set -e
uv run --all-extras ruff check --fix --silent --exit-zero
uv run --all-extras ruff format
uv run --all-extras ruff check
uv run --all-extras mypy .