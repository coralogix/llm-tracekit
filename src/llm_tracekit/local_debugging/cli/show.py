import json
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.json import JSON
from llm_tracekit.local_debugging.filesystem_spans import FilesystemSpans
from llm_tracekit.local_debugging.utilities import _format_timestamp, _parse_conversation_from_span


def show_span(traces_directory: Optional[str], span_id):
    filesystem_spans = FilesystemSpans(traces_directory)
    spans = filesystem_spans.get_spans()

    console = Console()

    expected_span = [span for span in spans if span["span_id"].startswith(span_id)]
    if len(expected_span) != 1:
        console.print(
            f"[red]Session number {span_id} not found. Run 'list' command to see available sessions.[/red]"
        )
        return
    
    span = expected_span[0]

    # Show general session id identifier
    console.print(
        Panel(
            f"[bold]Session ID:[/bold] {span['span_id']}",
            title="Session Details",
            subtitle=f"Created: {_format_timestamp(span['timestamp'])}",
        )
    )

    _show_span(span)


def _show_span(span: dict):
    console = Console()

    conversation = _parse_conversation_from_span(span)  # noqa: F821

    for i, message in enumerate(conversation):
        msg_type = message.get("type", "message")
        role = message.get("role", "unknown")

        # Set color based on role
        if role == "system":
            color = "cyan"
        elif role == "user":
            color = "green"
        elif role == "assistant":
            color = "yellow"
        elif role == "tool":
            color = "magenta"
        else:
            color = "white"

        # Display message based on type
        if msg_type == "message":
            content = message.get("content", "")
            header = f"[bold]{role.upper()}[/bold]"
            finish_reason = message.get("finish_reason")
            if finish_reason:
                header += f" (finish_reason: {finish_reason})"

            console.print(f"[{color}]{header}[/{color}]")

            # Handle code blocks in markdown
            if "```" in content:
                console.print(Markdown(content))
            else:
                console.print(content)

        elif msg_type == "tool_call":
            tool_name = message.get("tool_name", "unknown_tool")
            tool_arguments = message.get("tool_arguments", "{}")

            header = f"[bold]{role.upper()} → TOOL CALL:[/bold] [bold blue]{tool_name}[/bold blue]"
            console.print(f"[{color}]{header}[/{color}]")

            # Format and display arguments
            try:
                if isinstance(tool_arguments, str):
                    args_obj = json.loads(tool_arguments)
                    console.print(JSON(json.dumps(args_obj, indent=2)))
                else:
                    console.print(f"{tool_arguments}")
            except json.JSONDecodeError:
                console.print(f"{tool_arguments}")

        elif msg_type == "tool_response":
            content = message.get("content", "")
            tool_name = message.get("tool_name", "unknown_tool")

            header = f"[bold]TOOL RESPONSE:[/bold] [bold blue]{tool_name}[/bold blue]"
            console.print(f"[{color}]{header}[/{color}]")

            # Display tool response content
            try:
                if isinstance(content, str) and (
                    content.startswith("{") or content.startswith("[")
                ):
                    content_obj = json.loads(content)
                    console.print(JSON(json.dumps(content_obj, indent=2)))
                else:
                    console.print(content)
            except json.JSONDecodeError:
                console.print(content)

        # Add separator between messages
        if i < len(conversation) - 1:
            console.print("─" * 80)
