from datetime import datetime
from typing import Optional
from llm_tracekit.local_debugging.filesystem_spans import FilesystemSpans
from rich.console import Console
from rich.table import Table


def list_llm_conversations(traces_directory: Optional[str] = None):
    filesystem_spans = FilesystemSpans(traces_directory)
    sessions = filesystem_spans.get_sessions()

    console = Console()

    if len(sessions) == 0:
        console.print("[yellow]No LLM sessions found.[/yellow]")
        return

    table = Table(title="LLM Sessions")
    table.add_column("ID", style="cyan")
    table.add_column("Created", style="green")
    table.add_column("Model", style="yellow")
    table.add_column("# User Msgs", style="magenta")
    table.add_column("# Msgs", style="magenta")
    table.add_column("Total Tokens", style="blue")

    for trace_id in sessions:
        created_at = format_timestamp(sessions[trace_id][0]["timestamp"])

        # Find model name from spans
        model = "Unknown"
        total_tokens = 0

        seen_span_tokens = set()

        for span in sessions[trace_id]:
            attributes = span["attributes"]
            if "gen_ai.request.model" in attributes:
                model = attributes["gen_ai.request.model"]

            # Only check for separate input/output tokens
            if (
                "gen_ai.usage.input_tokens" in attributes
                and "gen_ai.usage.output_tokens" in attributes
            ):
                input_tokens = int(attributes["gen_ai.usage.input_tokens"])
                output_tokens = int(attributes["gen_ai.usage.output_tokens"])

                # Create a unique identifier for this span's token usage
                # Use the span ID if available, otherwise use a combination of tokens and timestamps
                span_id = span["span_id"]
                token_key = f"{span_id}:{input_tokens}:{output_tokens}"

                if token_key not in seen_span_tokens:
                    seen_span_tokens.add(token_key)
                    total_tokens += input_tokens + output_tokens

        # Count messages instead of spans
        conversation = _parse_conversation_from_span(span)
        message_count = len(conversation)

        # Count user messages specifically
        user_message_count = sum(1 for m in conversation if m.get("role") == "user")

        table.add_row(
            trace_id[:8],
            created_at,
            model,
            str(user_message_count),
            str(message_count),
            str(total_tokens) if total_tokens > 0 else "N/A",
        )

    console.print(table)


def format_timestamp(timestamp_ms: int) -> str:
    """Format a timestamp in milliseconds to a human-readable string.
    
    Args:
        timestamp_ms: Timestamp in milliseconds.
        
    Returns:
        Formatted timestamp string.
    """
    dt = datetime.fromtimestamp(timestamp_ms / 1000)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _parse_conversation_from_span(span: dict) -> list[dict]:
    conversation = []

    index = 0

    while True:
        if f"gen_ai.prompt.{index}.role" not in span["attributes"] or f"gen_ai.prompt.{index}.content" not in span["attributes"]:
            break

        conversation.append(
            {
                "role": span["attributes"][f"gen_ai.prompt.{index}.role"],
                "content": span["attributes"][f"gen_ai.prompt.{index}.content"],
            }
        )

        index += 1

    return conversation
