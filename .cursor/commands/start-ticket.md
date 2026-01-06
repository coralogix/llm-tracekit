# Start Work on Linear Ticket

When user runs `/start-ticket <TICKET_ID_OR_URL>` or provides a ticket ID/URL as a parameter, perform the following:

## Steps

### 1. Extract ticket identifier and get details from Linear

- Support both ticket IDs (e.g., "AIAPP-756") and Linear URLs (e.g., "https://linear.app/coralogix/issue/AIAPP-755/...")
- For URLs, extract the ticket identifier from the URL path (format: `/issue/<IDENTIFIER>/...`)
- Use `mcp_linear_get_issue` with the identifier to get full ticket details
- Extract from result: `id` (UUID), `identifier`, `title`, `description`, `gitBranchName`, `status`, `assignee`, `attachments`
- **IMPORTANT**: Always use the `gitBranchName` from Linear - never generate your own branch name

### 2. Update ticket status and assignment

- **Always update status to "In Progress"** when starting work on a ticket
- Only assign ticket to user if:
  - Ticket is currently unassigned (assignee is null/empty), OR
  - User explicitly requests assignment in the command (e.g., "assign it to me")
- Use `mcp_linear_update_issue` with:
  - `id`: The ticket ID (UUID from Linear, not the identifier)
  - `state`: "In Progress" (always set this when starting work)
  - `assignee`: "me" (only if conditions above are met)

### 3. Create and checkout branch

**ALWAYS** use the `gitBranchName` from the Linear issue response.

```bash
# Fetch latest from remote
git fetch origin

# Check if branch exists locally
git show-ref --verify --quiet refs/heads/<gitBranchName>
```

**If branch exists locally:**
```bash
git checkout <gitBranchName>
git pull origin <gitBranchName>  # Update with remote changes
```

**If branch exists only on remote:**
```bash
git checkout -b <gitBranchName> origin/<gitBranchName>
```

**If branch doesn't exist anywhere:**
```bash
git checkout -b <gitBranchName> origin/main
# or origin/master if main doesn't exist
```

### 4. Load ticket context

- Display ticket title and description to user
- Include any attachments or linked issues
- Extract JIRA ticket ID from attachments if present (format: "AIAP-XXX")

### 5. Confirm ready to work

Show the following to the user:
- "Ready to work on `<TICKET_ID>`: `<title>`"
- Branch name (the Linear-generated one)
- Ticket description
- Current assignee status
- JIRA ticket ID if found

### 6. Generate implementation plan

- Use the ticket `title` and `description` to create a comprehensive implementation plan
- Create the plan using Plan mode (do not execute changes)
- The plan should:
  - Break down the work into specific, actionable steps
  - Identify files that will likely need changes
  - Consider both frontend and backend if applicable
  - Include database migrations if schema changes are needed
  - Reference the ticket description and any requirements
  - Be specific about what needs to be changed and where
- Wait for user approval before implementing the plan

## Workflow Summary

```
1. Get ticket from Linear → Extract gitBranchName
2. Update status to "In Progress" → Assign if unassigned or requested
3. Fetch origin and create/checkout branch
4. Display ticket context to user
5. Generate implementation plan and wait for approval
```

## Usage Examples

- `/start-ticket DES-756` - Start work on ticket DES-756
- `/start-ticket https://linear.app/coralogix/issue/DES-755/...` - Start work using Linear URL
- `/start-ticket DES-756 and assign it to me` - Start work and explicitly assign
- `/start-ticket DES-756 assign` - Start work and assign (if unassigned)

## Important Notes

- **Always use Linear's provided branch name** - don't create your own
- If the branch already exists locally or remotely, check it out instead of creating new
- The dev environment should already be running (see `local-dev-env` rule)
