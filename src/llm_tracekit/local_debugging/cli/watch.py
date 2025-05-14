import os
from typing import Optional
from llm_tracekit.local_debugging.cli.show import _show_span
from llm_tracekit.local_debugging.filesystem_spans import FilesystemSpans

def watch(traces_directory: Optional[str]):
    filesystem_spans = FilesystemSpans(traces_directory)
    
    def on_new_trace_created(file_path: str):
        trace_id = os.path.basename(file_path)
        spans_created = filesystem_spans.get_spans_by_trace()[trace_id]
        for span in spans_created:
            _show_span(span)

    def on_span_added_to_trace(file_path: str, start_offset: int, end_offset: int):
        pass
    
    filesystem_spans.register_for_notifications(on_new_trace_created, on_span_added_to_trace)
