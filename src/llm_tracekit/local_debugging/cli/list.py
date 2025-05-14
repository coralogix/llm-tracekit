from typing import Optional
from llm_tracekit.local_debugging.filesystem_spans import FilesystemSpans
from rich.console import Console
from rich.table import Table

from llm_tracekit.local_debugging.utilities import _format_timestamp, _parse_conversation_from_span


def list_llm_conversations(traces_directory: Optional[str]):
    filesystem_spans = FilesystemSpans(traces_directory)
    spans = filesystem_spans.get_spans()

    console = Console()

    if len(spans) == 0:
        console.print("[yellow]No LLM sessions found.[/yellow]")
        return

    table = Table(title="LLM Sessions")
    table.add_column("ID", style="cyan")
    table.add_column("Created", style="green")
    table.add_column("Model", style="yellow")
    table.add_column("# User Msgs", style="magenta")
    table.add_column("# Msgs", style="magenta")
    table.add_column("Total Tokens", style="blue")

    for span in spans:
        created_at = _format_timestamp(span["timestamp"])

        model = span["attributes"].get("gen_ai.request.model", "Unknown")
        total_tokens = _calculate_tokens_usage(span)

        conversation = _parse_conversation_from_span(span)
        message_count = len(conversation)

        user_message_count = sum(1 for m in conversation if m.get("role") == "user")

        table.add_row(
            span["span_id"][:8],
            created_at,
            model,
            str(user_message_count),
            str(message_count),
            str(total_tokens) if total_tokens > 0 else "N/A",
        )

    console.print(table)

def _calculate_tokens_usage(span: dict) -> int:
    input_tokens = span["attributes"].get("gen_ai.usage.input_tokens")
    output_tokens = span["attributes"].get("gen_ai.usage.output_tokens")

    total_tokens = 0
    if input_tokens is not None:
        total_tokens = int(input_tokens)

    if output_tokens is not None:
        total_tokens += int(output_tokens)

    return total_tokens
