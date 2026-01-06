#!/bin/sh
set -e
uv run --all-extras ruff check
uv run --all-extras mypy
