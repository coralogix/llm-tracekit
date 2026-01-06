---
globs: *.py
alwaysApply: false
description: "Python style guide with examples and patterns"
---
# Style Guide

This document defines the Python style guide for the llm-tracekit project. It is based on analysis of the current codebase and should be used as a reference for all new code and refactoring efforts.

## Table of Contents

1. [Overview](#overview)
2. [Python Style Conventions](#python-style-conventions)
3. [Database Patterns](#database-patterns)
4. [FastAPI Patterns](#fastapi-patterns)
5. [Error Handling](#error-handling)
6. [Logging](#logging)
7. [Testing](#testing)
8. [Code Organization](#code-organization)
9. [Examples](#examples)
10. [Summary](#summary)
11. [Reference Implementation](#reference-implementation)
12. [Checking Code Against This Guide](#checking-code-against-this-guide)

## Overview

### Core Principles

- **Type Safety**: We requiere python 3.10, use type hints throughout
- **Async-First**: All I/O operations must be async
- **Explicit over Implicit**: Prefer clear, explicit code over clever abstractions

### Technology Stack

- **Python**: 3.10+ (using `|` union syntax, PEP 604)
- **Type Checking**: `mypy` (non-strict mode due to asyncpg limitations)

## Python Style Conventions

### Type Hints

Use Python 3.10+ type hints throughout. Prefer `|` union syntax over `Union`.

```python
# ✅ Good
def get_user(user_id: str | None) -> UserRead | None:
    ...

# ❌ Bad
from typing import Union
def get_user(user_id: Union[str, None]) -> Union[UserRead, None]:
    ...
```

**Required Type Hints:**
- All function parameters
- All return types (except when function returns nothing - no need for `-> None`)
- Class attributes
- Module-level variables (when not obvious)

**Type Hints for Complex Types:**

Even complex types like callables, generics, and nested types should be properly typed. Use `ParamSpec` and `TypeVar` to fully specify callable signatures without using `...`:

```python
from collections.abc import Awaitable, Callable
from typing import Concatenate, ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")
C = TypeVar("C", bound=BaseAgentContext)

# ✅ Good - fully typed decorator using ParamSpec
def metered_function_tool(
    *, tool_name: str, **decorator_kwargs
) -> Callable[[Callable[Concatenate[ToolContext[C], P], R]], FunctionTool]:
    """Drop-in replacement for `@function_tool` that adds tools metrics."""
    
    def decorator(
        fn: Callable[Concatenate[ToolContext[C], P], R],
    ) -> FunctionTool:
        # Implementation...
        return function_tool(**decorator_kwargs)(fn)
    
    return decorator

# ✅ Good - type aliases for callables with ParamSpec
AsyncRunAction = Callable[P, Awaitable[R]]
SyncRunAction = Callable[P, R]

async def run_action(action: AsyncRunAction[P, R]) -> R:
    return await action()

# ✅ Good - callable that prepends parameters using Concatenate
def with_context(
    fn: Callable[P, R]
) -> Callable[Concatenate[Context, P], R]:
    def wrapper(ctx: Context, *args: P.args, **kwargs: P.kwargs) -> R:
        return fn(*args, **kwargs)
    return wrapper
```

**Avoid:**
- Using `...` in callable types (e.g., `Callable[..., Any]`) - use `ParamSpec` instead
- Using `Any` for callable parameters when the signature is known
- Omitting type hints for complex nested types
- Using `Callable` without specifying parameter and return types when they're known

### Async/Await Patterns

**Always use async for I/O operations:**

```python
# ✅ Good
async def fetch_user(db: DBConnection, user_id: str) -> UserRead:
    record = await db.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
    ...

# ❌ Bad - blocking I/O
def fetch_user(db: DBConnection, user_id: str) -> UserRead:
    record = db.fetchrow("SELECT * FROM users WHERE id = $1", user_id)  # Wrong!
    ...
```

**Concurrent Operations:**
```python
# ✅ Good - use asyncio.gather for concurrent operations
results = await asyncio.gather(
    fetch_user_data(db, user_id),
    fetch_user_settings(db, user_id),
    return_exceptions=False  # Raise exceptions immediately
)
```

### Naming Conventions

- **Functions/Methods**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private methods/functions**: `_leading_underscore` (applies to both class methods and module-level helper functions)
- **Type aliases**: `PascalCase` (e.g., `DBConnection`, `UserIdDep`)

```python
# ✅ Good
class ChatController:
    async def create_chat(self, ...) -> ChatRead:
        ...
    
    async def _validate_data_source_access(self, ...):
        ...  # Private method - no return type needed when function returns nothing

# ✅ Good - module-level private helper functions
def _get_s3_key(account_id: str, object_id: UUID, object_type: str) -> str:
    return f"{account_id}/{object_type}/{object_id}"

MAX_RETRIES = 10
DEFAULT_TIMEOUT_SECONDS = 30
```

### Classes

**Classes should not be used purely for namespacing.** Use classes only when they:
- Manage state (hold instance variables that persist across method calls and change over time)
- Provide a convenient API (group related methods that share common parameters or context)

```python
# ✅ Good - class provides convenient API (groups methods sharing common context)
class ChatController:
    def __init__(self, account_id: str, user_id: str):
        self._account_id = account_id
        self._user_id = user_id
    
    async def create_chat(self, db: DBConnection, ...) -> ChatRead:
        # Methods share common context (account_id, user_id) passed to __init__
        ...

# ✅ Good - class manages actual state
class ConnectionPool:
    def __init__(self):
        self._connections: list[Connection] = []
        self._max_size = 10
    
    async def acquire(self) -> Connection:
        # Manages state: connection pool that changes over time
        ...
    
    async def release(self, conn: Connection):
        # Updates internal state
        ...

# ❌ Bad - class used only for namespacing
class ArtifactUtils:
    @staticmethod
    async def read_from_s3(key: str) -> dict:
        ...
    
    @staticmethod
    async def upload_to_s3(key: str, data: BaseModel):
        ...

# ✅ Good - use module-level functions instead
async def read_object_from_s3(key: str) -> dict:
    ...

async def _upload_object_to_s3(key: str, data: BaseModel):
    ...
```

### Early Returns

Use early returns for guard clauses to reduce nesting and improve readability:

```python
# ✅ Good - early return for guard clause
async def delete_artifacts(
    db: asyncpg.Connection,
    account_id: str,
    chat_ids: list[UUID] | None = None,
) -> None:
    if chat_ids is not None and len(chat_ids) == 0:
        return
    
    # Continue with main logic
    ...
```

### Docstrings

Use docstrings for public functions, classes, and complex logic:

```python
# ✅ Good
async def get_or_create_account_settings(db: DBConnection) -> AccountSettings:
    """Get or create account settings for the current account.

    This is a get-or-insert query that can handle conflicts (in case of multiple
    invocations before the row exists) and is only slightly less efficient than a
    simple SELECT.

    Args:
        db: Database connection with account_id context set

    Returns:
        AccountSettings for the current account
    """
    ...
```

**Important:** Avoid trailing whitespace in docstrings. Blank lines within docstrings should not contain any spaces or tabs. This prevents linting errors and reduces cleanup steps.

### Function Complexity

**Break up long functions into smaller helper functions.** If a function is too long or complex, extract logical parts into private helper functions.

**Benefits of breaking up functions:**
- Improved readability and maintainability
- Easier to test individual pieces
- Better code reuse
- Clearer separation of concerns

### Eliminating Code Duplication

**Identify and extract repeated patterns across multiple functions.** When you see similar code in multiple places, create a helper method to eliminate duplication.

```python
# ❌ Bad - repeated pattern across multiple methods
async def get_metrics_list(self, start_time: str | None = None, end_time: str | None = None) -> list[str]:
    url = f"{self.metrics_base_url}/metrics/api/v1/label/__name__/values"
    headers = {
        **(await self.get_auth_headers()),
        "Content-Type": "application/x-www-form-urlencoded",
    }
    params = {}
    if start_time:
        params["start"] = start_time
    if end_time:
        params["end"] = end_time
    response = await self._client.get(url, headers=headers, params=params, timeout=self.timeout)
    response.raise_for_status()
    return response.json()["data"]

async def get_metric_labels(self, metric_name: str, ...) -> list[str]:
    url = f"{self.metrics_base_url}/metrics/api/v1/labels"
    headers = {
        **(await self.get_auth_headers()),
        "Content-Type": "application/x-www-form-urlencoded",
    }
    params = {"match": metric_name}
    # ... same pattern repeated
    response = await self._client.get(url, headers=headers, params=params, timeout=self.timeout)
    response.raise_for_status()
    return response.json()["data"]

# ✅ Good - extract common pattern into helper method
async def _make_get_request(
    self,
    url: str,
    params: dict[str, str] | None = None,
    content_type: str = "application/x-www-form-urlencoded",
) -> dict:
    """Make a GET request to Coralogix API."""
    headers = {
        **(await self.get_auth_headers()),
        "Content-Type": content_type,
    }
    response = await self._client.get(url, headers=headers, params=params, timeout=self.timeout)
    response.raise_for_status()
    return response.json()

async def get_metrics_list(self, start_time: str | None = None, end_time: str | None = None) -> list[str]:
    url = f"{self.metrics_base_url}/metrics/api/v1/label/__name__/values"
    params: dict[str, str] = {}
    if start_time:
        params["start"] = start_time
    if end_time:
        params["end"] = end_time
    return (await self._make_get_request(url, params if params else None))["data"]

async def get_metric_labels(self, metric_name: str, ...) -> list[str]:
    url = f"{self.metrics_base_url}/metrics/api/v1/labels"
    params: dict[str, str] = {"match": metric_name}
    # ... add time params if needed
    return (await self._make_get_request(url, params))["data"]
```

**Guidelines for extracting helpers:**
- Look for repeated patterns: similar parameter building, header construction, request/response handling
- Make helpers flexible with optional parameters and sensible defaults
- Return general types (e.g., `dict`) and let callers extract what they need
- Start specific, then generalize when you see the pattern repeated elsewhere
- Use private helper methods (leading underscore) for internal reuse

**Benefits:**
- Single source of truth for common operations
- Easier to modify behavior in one place
- Reduced chance of inconsistencies
- Better testability (test the helper once)


## Testing

### Test Structure

**Test file organization:**
```
tests/
├── routes/
│   ├── test_chats.py
│   └── test_users.py
└── conftest.py  # Shared fixtures
```

## Code Organization

### Module Length

**Keep modules focused and reasonably sized.** While there's no strict line limit, modules should generally:
- Focus on a single responsibility or closely related set of responsibilities
- Be easy to navigate and understand
- Not exceed ~500-800 lines for most modules

**When a module becomes too long, consider:**
- Splitting into multiple modules by functionality (e.g., separate query functions from business logic)
- Extracting related classes or functions into their own modules
- Grouping related utilities into submodules

```python
# ❌ Bad - single module with too many responsibilities
# clients/coralogix_grpc.py (2000+ lines)
# Contains: client setup, query building, result processing, error handling, etc.

# ✅ Good - split into focused modules
# clients/coralogix_grpc/
#   ├── __init__.py          # Public API
#   ├── client.py            # Client setup and connection
#   ├── query_builder.py     # Query construction
#   ├── result_processor.py  # Result processing
#   └── errors.py            # Error handling
```

**Exception:** Some modules may legitimately be longer (e.g., generated code, protocol implementations). Use judgment based on maintainability and readability.

## Summary

This style guide captures the current patterns and conventions in the Olly backend codebase. When writing new code or refactoring existing code:

1. **Follow the patterns** outlined in this guide
2. **Use type hints** throughout (Python 3.12+ syntax)
3. **Use async/await** for all I/O operations
4. **Use account_* views** for SELECT queries, `CURRENT_SETTING('olly.account_id')` for INSERTs
5. **Handle errors explicitly** - use domain-specific exceptions only when other code expects to catch them
6. **Log appropriately** with proper context
7. **Write tests** following the established patterns

Remember: The current codebase is not perfect. This guide represents the target state. When refactoring, use this guide as the reference for what "good" looks like.

## Reference Implementation

For good examples of code that adheres to this style guide, see:

- `libs/common/src/common/artifacts.py` - Demonstrates proper use of type hints, async patterns, database queries with account views, transactions with external operations, TypeAdapter for Union types, module-level private helpers, early returns, and appropriate exception handling.

- `libs/common/src/common/clients/redis.py` - Demonstrates proper type hints (including module-level variables), complete docstrings for all public functions and classes, async context managers, and appropriate exception handling.

- `libs/common/src/common/clients/coralogix.py` - Demonstrates eliminating code duplication through helper methods, proper type hints, complete docstrings, specific exception handling (avoiding bare `Exception`), and flexible helper methods with optional parameters.

## Checking Code Against This Guide

When reviewing or refactoring code, systematically check for adherence to this style guide:

### Quick Reference Checklist

When reviewing a file, quickly check:
- [ ] All functions have type hints (parameters + return types, except `-> None`)
- [ ] All public functions/classes have docstrings
- [ ] No bare `Exception` catches (use specific exceptions)
- [ ] Repeated patterns extracted into helpers
- [ ] Module length reasonable (~500-800 lines)
- [ ] All I/O operations are async
- [ ] Database SELECTs use `account_*` views

### Checklist

1. **Type Hints**
   - All function parameters have type hints
   - All return types are specified (except `-> None` is not needed)
   - Module-level variables have type hints when not obvious
   - Complex types (callables, generics) are properly typed

2. **Docstrings**
   - All public functions have docstrings with Args and Returns sections
   - All public classes have docstrings
   - Complex logic has explanatory comments
   - No trailing whitespace in docstrings

3. **Code Duplication**
   - Repeated patterns are extracted into helper methods
   - Helper methods are flexible with optional parameters
   - Single source of truth for common operations

4. **Exception Handling**
   - Specific exceptions are used (avoid bare `Exception`)
   - Domain-specific exceptions only used when other code expects to catch them
   - Standard exceptions (`ValueError`, `RuntimeError`, `KeyError`) for internal errors

5. **Module Organization**
   - Modules are focused and reasonably sized (~500-800 lines)
   - Related functionality is grouped logically
   - Private helpers use `_leading_underscore` naming

6. **Async/Await**
   - All I/O operations are async
   - `asyncio.gather` used for concurrent operations
   - Background tasks use `create_background_task`

7. **Database Patterns**
   - SELECT queries use `account_*` views
   - INSERT queries use `CURRENT_SETTING('olly.account_id')`
   - Transactions properly handle external operations (S3, etc.)

### Workflow

When refactoring or reviewing code:

1. **Read the file** to understand its purpose and structure
2. **Check against the checklist** above
3. **Identify missing patterns** (type hints, docstrings, etc.)
4. **Look for duplication** that could be extracted
5. **Verify exception handling** is appropriate
6. **Check module length** - consider splitting if too long
7. **Reference implementations** - compare with examples listed above

### Example Review Process

```python
# 1. Check type hints
async def get_user(user_id: str) -> UserRead:  # ✅ Good
async def get_user(user_id):  # ❌ Missing type hints

# 2. Check docstrings
async def get_user(user_id: str) -> UserRead:
    """Get user by ID."""  # ✅ Good
    # ❌ Missing docstring

# 3. Check for duplication
# If you see similar patterns in multiple methods, extract a helper

# 4. Check exception handling
except Exception:  # ❌ Too broad
except (ValueError, KeyError):  # ✅ Specific
```
