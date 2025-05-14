from typing import Optional
from llm_tracekit.local_debugging.filesystem_spans import FilesystemSpans

def watch(traces_directory: Optional[str]):
    filesystem_spans = FilesystemSpans(traces_directory)
    
    def on_new_trace_created(file_path: str):
        pass

    def on_span_added_to_trace(file_path: str, start_offset: int, end_offset: int):
        pass
    
    filesystem_spans.register_for_notifications(on_new_trace_created, on_span_added_to_trace)
