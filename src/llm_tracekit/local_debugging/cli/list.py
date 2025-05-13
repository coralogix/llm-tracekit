from llm_tracekit.local_debugging.filesystem_spans import DEFAULT_TRACES_DIRECTORY

def list_llm_conversations(traces_directory: str | None):
    if traces_directory is None:
        traces_directory = DEFAULT_TRACES_DIRECTORY

    print(f"listing {traces_directory}")
