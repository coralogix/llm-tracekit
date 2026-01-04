# Code Checks

When user runs `/code-checks`, run through the code checks to ensure code quality before committing.

## Steps

### 1. Fix Linting Issues

**Run lint fix to automatically resolve formatting and linting issues:**

```bash
uv run scripts/lint-fix.sh
```

- This will fix auto-fixable linting issues across the codebase
- Review any remaining linting errors that couldn't be auto-fixed
- Fix them manually if needed

### 2. Run Tests (In Order)

**Run tests in the following order, fixing any failures before proceeding:**

```bash
uv run pytest tests/
```

### 3. Stage Changes

**Stage all modified files:**

```bash
git add .
```

- Review what files are staged with `git status`
- Ensure only relevant files are staged (no accidental changes)
- If needed, unstage files with `git reset <file>`

### 4. Commit Changes

**Create a meaningful commit message:**

```bash
git commit -m "Meaningful commit message based on the ticket"
```

**Commit message guidelines:**
- Use present tense ("Add feature" not "Added feature")
- Be descriptive but concise
- Reference the ticket/issue if applicable
- Examples:
  - `"Add user profile page with avatar upload"`
  - `"Fix login redirect issue after email verification"`
  - `"Update API endpoint to return paginated results"`

## Complete Workflow Example

```bash
# 1. Fix linting
uv run scripts/lint-fix.sh

# 2. Run tests
uv run pytest tests/

# If lint fails → pnpm lint:fix → rerun ALL tests
# If tests fail → fix tests → rerun lint check
# Repeat until BOTH pass together without changes

# 3. Stage changes
git add .

# 4. Commit
git commit -m "Add user profile page with avatar upload"
```

## Usage

- `/code-checks` - Run the full code checks

## Important Notes

- **Never skip tests** - All relevant tests must pass before committing
- **Unit tests are API-only** - Only run unit tests if you changed backend code
- **Tests AND lint must pass together** - Both must pass without changes between runs
- **Iterative fix process** - Fix lint → rerun tests, fix tests → rerun lint, repeat until both pass
- **Don't proceed until both pass** - Do NOT stage/commit until tests AND lint both pass together
- **Don't commit broken code** - Ensure everything passes before committing
- **Meaningful commits** - Commit messages should clearly describe what changed


## Linting Details

### What `uv run scripts/lint-fix.sh` Does

This runs linting for all packages in the monorepo:
- `@llm-tracekit/` - Python (ruff)


### Common Linting Issues

#### Python

1. **Trailing whitespace**:
   - Common in migration files
   - Fix: Remove trailing spaces at end of lines
   - Example: `UPDATE data_sources ` → `UPDATE data_sources`

2. **Line length**:
   - Keep lines under character limit
   - Break long SQL queries across multiple lines

3. **Import ordering**:
   - Ruff will auto-fix import order


## Anti-Patterns (Don't Do This)

❌ Committing without running tests
❌ Committing with generic messages like "fix" or "update"
❌ Committing without fixing linting errors
❌ Pushing code that fails tests

## Good Practices (Do This)

✅ Run `uv run lint-fix.sh` first and fix all issues
✅ Run unit tests from `tests/` if you changed instrumentations code
✅ Fix lint → rerun ALL tests, fix tests → rerun lint check
✅ Repeat until BOTH pass without any changes between runs
✅ Use meaningful commit messages based on the ticket
✅ Ensure all tests AND lint pass flawlessly together before committing

