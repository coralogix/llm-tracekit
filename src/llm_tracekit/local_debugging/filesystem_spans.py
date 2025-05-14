import itertools
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

    def get_spans(self) -> List[Dict]:
        trace_id_to_spans = self.get_spans_by_trace()
        spans = list(itertools.chain.from_iterable(trace_id_to_spans.values()))

        return spans

    def get_spans_by_trace(self) -> Dict[str, List[Dict]]:
        if not os.path.exists(self._traces_directory):
            return {}

        spans: Dict[str, List[Dict]] = {}

        for trace_id in os.listdir(self._traces_directory):
            full_path = os.path.join(self._traces_directory, trace_id)

            with open(full_path, "rt") as trace_file:
                raw_sessions_data = trace_file.readlines()

            if trace_id not in spans and len(raw_sessions_data) > 0:
                spans[trace_id] = []
            
            for raw_session in raw_sessions_data:
                span = json.loads(raw_session)
                spans[trace_id].append(span)

        return spans

    def save_span(self, span: dict):
        """Save a span to the local filesystem.
        
        Args:
            span: the span to save
        """
        # Save to file
        filepath = os.path.join(self._traces_directory, span['trace_id'])
        with open(filepath, "at") as output_file:
            output_file.write(json.dumps(span) + "\n")
