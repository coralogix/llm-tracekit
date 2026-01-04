# llm-tracekit Self-Improvement Command

You are an expert in prompt engineering, specializing in optimizing AI code assistant instructions. Your task is to analyze and improve the instructions for Cursor in this workspace.

## Task

Analyze session history and workspace instructions to identify patterns, inefficiencies, and improvement opportunities. Then implement approved changes.

**This command differs from reactive instruction capture:**
- **Reactive capture**: Catches explicit instructions in real-time
- **This command**: Proactive, analyzes full session to find unstated patterns

---

## Phase 1: Analysis

Review in order:

1. **Recent Chat History** - Analyze exchanges to identify patterns
2. **Current Instructions:**
   - `.cursor/rules/**/*.md` (specific rule files)
   - `.cursor/README.md` (workspace documentation)
3. **Existing Commands:** `.cursor/commands/*.md`
4. **Configuration:** Any Cursor-specific config files in the workspace

### Analysis Focus

Look for:
- **Contradictions** between instruction files
- **Patterns** where Cursor struggled or needed multiple attempts
- **Missing workflows** that recur but lack guidance
- **Pre-approval opportunities** for frequently used tools/permissions
- **Outdated patterns** (deprecated tools, old syntax)
- **Gaps** in coverage for common tasks
- **Inconsistencies** in formatting or structure across rules/commands

---

## Phase 2: Present Findings

For each finding include:
- **Issue:** Problem with specific examples from chat history
- **Proposed Change:** Exact text modifications
- **Location:** File path and section
- **Impact & Priority:** Expected improvement (High/Medium/Low)

Wait for user approval before implementing.

---

## Phase 3: Implementation

For approved changes: show diff, apply using Edit/Write, verify, and track completion.

---

## Safety & Output

**Safety:**
- Preserve existing functionality unless explicitly problematic
- Get user approval for breaking changes
- Verify each change before moving to the next
- Maintain consistency with existing patterns

**Summary Output:**
Include: total findings, approval status, changes by file, and next steps.

---

## Context

This is the llm-tracekit codebase - a Coralogix AI instrumentations monorepo:
- **Instrumentations**: Python 3.10 in `src/llm-tracekit/`
- Uses `uv` for Python package management
- Uses `ruff` for Python linting

---

## Begin Analysis

Start by reviewing the recent chat history and current instructions. Present your findings one at a time, starting with the highest priority improvements.

