from typing import Dict, List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from llm_tracekit.local_debugging.cli.show import _show_span
from llm_tracekit.local_debugging.filesystem_spans import FilesystemSpans


class Callbacks:
    def __init__(self, filesystem_spans):
        self._filesystem_spans = filesystem_spans
        self._previous_spans = {}
        self._console = Console()
        self._first_span_printed = False

    def on_trace_change(self, trace_id: str):
        current_spans = self._filesystem_spans.get_spans_by_trace()
        new_spans = self._get_new_spans(
            current_spans.get(trace_id, []), self._previous_spans.get(trace_id, [])
        )

        for span in new_spans:
            if self._first_span_printed:
                separator = Text("✧ NEXT SPAN ✧", style="bold cyan")
                self._console.print(
                    Panel(separator, border_style="cyan", expand=True, padding=(0, 0))
                )

            _show_span(span)

            self._first_span_printed = True

        self._previous_spans = current_spans

    @staticmethod
    def _get_new_spans(
        current_spans: List[Dict], previous_spans: List[Dict]
    ) -> List[Dict]:
        current_spans_ids = [span["span_id"] for span in current_spans]
        previous_spans_ids = [span["span_id"] for span in previous_spans]

        new_span_ids = set(current_spans_ids) - set(previous_spans_ids)
        return [span for span in current_spans if span["span_id"] in new_span_ids]


def watch(traces_directory: Optional[str]):
    filesystem_spans = FilesystemSpans(traces_directory)
    callbacks = Callbacks(filesystem_spans)

    filesystem_spans.listen_for_span_changes(callbacks.on_trace_change)
