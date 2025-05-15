import itertools
import json
import os
import time
from typing import Dict, List, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

DEFAULT_TRACES_DIRECTORY = "llm-traces"


class FileChangesHandler(FileSystemEventHandler):
    def __init__(self, on_trace_change):
        self.on_trace_change = on_trace_change

        self._path_to_last_position = {}

    def on_created(self, event):
        if event.is_directory:
            return

        self.on_trace_change(os.path.basename(event.src_path))

    def on_modified(self, event):
        if event.is_directory:
            return

        self.on_trace_change(os.path.basename(event.src_path))


class FilesystemSpans:
    def __init__(self, traces_directory: Optional[str] = None):
        if traces_directory is None:
            traces_directory = DEFAULT_TRACES_DIRECTORY

        if not os.path.exists(traces_directory):
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

        for trace_id in self._list_trace_files():
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
        filename = os.path.join(self._traces_directory, span["trace_id"])
        with open(f"{filename}.jsonl", "at") as output_file:
            output_file.write(json.dumps(span) + "\n")

    def clear_all(self):
        if not os.path.exists(self._traces_directory):
            return

        file_names = self._list_trace_files()

        for file_name in file_names:
            os.remove(os.path.join(self._traces_directory, file_name))

    def listen_for_span_changes(self, on_trace_change):
        """Blocks forever"""
        handler = FileChangesHandler(on_trace_change)
        observer = Observer()
        observer.schedule(handler, self._traces_directory, recursive=False)
        observer.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()

    def _list_trace_files(self) -> List[str]:
        file_names = os.listdir(self._traces_directory)
        return [file_name for file_name in file_names if file_name.endswith(".jsonl")]
