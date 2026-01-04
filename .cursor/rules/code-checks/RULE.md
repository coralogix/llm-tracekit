---
description: "Require code checks to pass before declaring work as complete or fixed"
alwaysApply: true
---

# Code Checks

## Core Principle

**Never declare that work is finished, fixed, or complete without running code checks first.**

## When to Run Code Checks

Before declaring that any implementation is complete, fixed, or finished:

1. **Run `/code-checks` command** - This runs linting, tests, and commits changes
2. **Verify all checks pass** - Both tests AND lint must pass together
3. **Only then declare work complete**

## Important

- Do NOT claim something is "done" or "fixed" until `/code-checks` passes
- Do NOT proceed to next tasks until current work passes checks
- Code must be committed - uncommitted code is not complete

## Related Rules

- **`pre-completion-testing`** - After code checks pass, also verify changes work correctly using Playwright (UI) or API/DB queries (backend). Both rules should be followed before declaring work complete.
