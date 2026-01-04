---
description: "Instructions for listing and filtering Linear tickets"
alwaysApply: false
---

# Ticket Listing Instructions

## Listing Tickets

When asked to list tickets:
- **Default behavior**: Always search for tickets in "Todo" or "In Progress" status unless explicitly stated otherwise
- Use `mcp_linear_list_issues` with appropriate filters:
  - Filter by status: `state` parameter with status IDs for "Todo" and "In Progress"
  - Filter by cycle: **Only if cycles exist** - Use `mcp_linear_list_cycles` to check for current cycle, then use `cycle` parameter if available
  - Filter by assignee: Use `assignee` parameter with user ID or "me" for user's tickets

**Cycle Handling**:
- First check if the team has cycles: `mcp_linear_list_cycles` with `type="current"`
- If a current cycle exists, filter by it
- If no cycles exist or no current cycle, don't use the `cycle` parameter

## Example Queries

- "List my tickets" → Filter by assignee="me" AND status="In Progress" or "Todo" (check for cycle first, include if exists)
- "List tickets in current cycle" → Check for current cycle, filter by it AND status="In Progress" or "Todo"
- "List all tickets" → Only then list all statuses (explicitly stated)

## Starting Work on a Ticket

Use the `/start-ticket` command. See `.cursor/commands/start-ticket.md` for the full workflow.
