from datetime import datetime
import json
import os
from typing import Any

DEFAULT_TRACES_DIRECTORY = "llm-traces"


class FilesystemSpans:
    def __init__(self, traces_directory: str | None):
        if traces_directory is None:
            traces_directory = DEFAULT_TRACES_DIRECTORY
        elif not os.path.exists(traces_directory):
            os.makedirs(traces_directory, exist_ok=True)

        self._traces_directory = traces_directory

    def get_sessions(self) -> list[dict]:
        if not os.path.exists(self._traces_directory):
            return []

        sessions = []

        for file_name in os.listdir(self._traces_directory):
            full_path = os.path.join(self._traces_directory, file_name)6

            with open(full_path, "rt") as trace_file:
                session = json.load(trace_file)

            sessions.append(session)

        return sessions

    def save_span(self, span: dict):
        """Save a span to the local filesystem.
        
        Args:
            span: the span to save
        """
        # Create a filename with timestamp and trace id
        timestamp = datetime.fromtimestamp(span["timestamp"] / 1000).strftime("%Y%m%d%H%M%S")
        
        # Save to file
        filepath = os.path.join(self._traces_directory, span['trace_id'])
        with open(filepath, "at") as output_file:
            output_file.write(json.dumps(span) + "\n")
