# Create Pull Request

When user runs `/create-pr` or `/pr`, create a pull request with proper formatting and JIRA linking.

## Core Principle

**Never open a PR without ensuring code quality, tests pass, and proper git hygiene.**

The PR workflow is split into two parts:
1. **Code Checks** (`/code-checks`) - Ensures code quality before committing
2. **Create PR** (`/create-pr` or `/pr`) - Creates the pull request with proper formatting

Always complete the code checks before creating a PR.

## Prerequisites

Before creating a PR, ensure you've completed the code checks (`/code-checks`). This command assumes code is already committed and ready for PR creation.

**See:** `.cursor/commands/code-checks.md` for detailed steps on running code checks.

## Steps

1. **Get current branch name**:
   - Run: `git rev-parse --abbrev-ref HEAD`
   - Extract Linear ticket ID from branch name (format: `des-XXX` or `DES-XXX`)

2. **Push current branch**:
   - Run: `git push -u origin <branch-name>`
   - This ensures the branch is available on remote for PR creation

3. **Get ticket details from Linear**:
   - Use `mcp_linear_list_issues` to find the ticket by identifier
   - Search for ticket with matching identifier (e.g., "DES-756")
   - Extract: `title`, `description`, `attachments` (for JIRA ID)

4. **Extract JIRA ticket ID**:
   - Check ticket attachments for JIRA link (format: "DES-XXX")
   - Or check ticket description for JIRA reference
   - If user provided JIRA ID as parameter, use that

5. **Generate PR title**:
   - Format: `<LINEAR_TICKET_ID> | <ticket_title>`
   - Example: `DES-756 | Rename Personal/Organizational data sources to Private/Shared`

6. **Generate PR description**:
   - Start with ticket description if available
   - Add summary of changes based on:
     - Recent commit messages: `git log --oneline origin/master...HEAD`
     - Files changed: `git diff --name-only origin/master...HEAD`
     - Conversation context (what was discussed and implemented)
     - Any additional context provided by user in the command
   - Structure the description:
     ```markdown
     ## Summary
     Brief overview of what was changed
     
     ## Changes
     - [list changes]
     
     ## Testing
     - [testing notes]
     
     ## JIRA
     <JIRA_TICKET_ID>
     ```

7. **Create PR**:
   - Run: `gh pr create --title "<TITLE>" --body "<DESCRIPTION>"`
   - Extract the PR URL from the output
   - **Display the PR URL as a markdown link**: Format as `[PR #<NUMBER>](<URL>)` when showing to the user
   - Example: `[PR #809](https://github.com/coralogix/llm-tracekit/pull/809)`

8. **Add JIRA comment**:
   - Run: `gh pr comment <PR_NUMBER> --body "JIRA: <JIRA_TICKET_ID>"`
   - Get PR number from the `gh pr create` output

## Complete Workflow Example

```bash
# Step 1: Run code checks
/code-checks
# This will:
# - Fix linting
# - Run tests
# - Verify tests AND lint pass together
# - Stage and commit changes

# Step 2: Create PR
/create-pr
# This will:
# - Push branch to remote
# - Extract Linear ticket details
# - Generate PR title and description
# - Create PR with JIRA linking
```

## Usage Examples

- `/create-pr` - Create PR with auto-detected ticket and JIRA ID
- `/pr` - Short form of create-pr
- `/create-pr JIRA: DES-606` - Create PR with explicit JIRA ID
- `/create-pr with additional context about testing` - Create PR with extra context in description

## Important Notes

- **Complete code checks first** - Always run `/code-checks` before `/create-pr`
- **Never skip tests** - All relevant tests must pass before opening a PR
- **Meaningful PR descriptions** - Include clear summary, changes, and testing notes
- **JIRA linking** - Always include JIRA ticket ID in PR description and comment

## Anti-Patterns (Don't Do This)

❌ Creating PR without running code checks
❌ Opening PR without running tests
❌ Opening PR without fixing linting errors
❌ Creating PR with generic or unclear descriptions
❌ Skipping JIRA linking in PR

## Good Practices (Do This)

✅ Run `/code-checks` first to ensure code quality
✅ Run `/create-pr` after completing the checks
✅ Include clear PR description with summary, changes, and testing notes
✅ Always include JIRA ticket ID in PR
✅ Use meaningful PR titles with Linear ticket ID
✅ Ensure all tests AND lint pass flawlessly together before opening PR
