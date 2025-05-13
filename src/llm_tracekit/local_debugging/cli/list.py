from llm_tracekit.local_debugging.filesystem_spans import FilesystemSpans

def list_llm_conversations(traces_directory: str | None):
    filesystem_spans = FilesystemSpans(traces_directory)
    sessions = filesystem_spans.get_sessions()

    print(f"Sessions: {sessions}")
