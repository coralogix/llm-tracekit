import json
import os
from typing import Dict, List, Optional

DEFAULT_TRACES_DIRECTORY = "llm-traces"


class FilesystemSpans:
    def __init__(self, traces_directory: Optional[str] = None):
        if traces_directory is None:
            traces_directory = DEFAULT_TRACES_DIRECTORY
        elif not os.path.exists(traces_directory):
            os.makedirs(traces_directory, exist_ok=True)

        self._traces_directory = traces_directory

    def get_sessions(self) -> Dict[str, Dict]:
        if not os.path.exists(self._traces_directory):
            return []

        sessions: Dict[List[Dict]] = {}

        for trace_id in os.listdir(self._traces_directory):
            full_path = os.path.join(self._traces_directory, trace_id)

            with open(full_path, "rt") as trace_file:
                raw_sessions_data = trace_file.readlines()

            if trace_id not in sessions and len(raw_sessions_data) > 0:
                sessions[trace_id] = []
            
            for raw_session in raw_sessions_data:
                session = json.loads(raw_session)
                sessions[trace_id].append(session)

        return sessions

    def save_span(self, span: dict):
        """Save a span to the local filesystem.
        
        Args:
            span: the span to save
        """
        # Save to file
        filepath = os.path.join(self._traces_directory, span['trace_id'])
        with open(filepath, "at") as output_file:
            output_file.write(json.dumps(span) + "\n")
