import json
import os
import time
from datetime import datetime
from typing import Dict, Any

from opentelemetry.trace import SpanKind

from llm_tracekit.local_debugging.filesystem_spans import FilesystemSpans

GENAI_TAG_NAME = "gen_ai.system"

class LocalSpanExporter:
    """Exports traces to the local filesystem for debugging purposes.
    
    This exporter captures all OpenAI API calls and saves them as JSON files
    in the specified directory, allowing developers to debug their LLM applications
    without needing to connect to Coralogix.
    """
    
    def __init__(self, traces_directory: str | None):
        """Initialize the exporter.
        
        Args:
            traces_directory: Directory where traces will be stored. Defaults to ~/.coralogix-ai/traces.
        """
        self._filesystem_spans = FilesystemSpans(traces_directory)
    
    def export(self, span):
        """Export a span to the local filesystem.
        
        Args:
            span: The span to export.
        """
        # Only process CLIENT spans (outgoing OpenAI API calls)
        if span.kind != SpanKind.CLIENT:
            return
        
        # Extract span metadata
        trace_id = format(span.context.trace_id, "032x")

        span_id = format(span.context.span_id, "016x")
        parent_id = format(span.parent.span_id, "016x") if span.parent else None
        name = span.name
        attributes = span.attributes
        
        # Basic validation
        if not name or not attributes:
            return
        
        # Check if this is a generative AI call
        if GENAI_TAG_NAME not in attributes:
            return
        
        timestamp = int(time.time() * 1000)
        
        # Preserve all span information
        span_data = {
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_id": parent_id,
            "name": name,
            "timestamp": timestamp,
            "start_time": span.start_time,
            "end_time": span.end_time,
            "duration_ms": (span.end_time - span.start_time) / 1000000,  # Convert to milliseconds
            "status": {
                "status_code": span.status.status_code.name if hasattr(span.status, "status_code") else None,
                "description": span.status.description if hasattr(span.status, "description") else None
            },
            # Store all attributes as they are without filtering
            "attributes": dict(attributes),
            # Include resource attributes
            "resource": {k: v for k, v in span.resource.attributes.items()} if hasattr(span, "resource") else {},
            # Include events and links if they exist
            "events": [
                {
                    "name": event.name,
                    "timestamp": event.timestamp,
                    "attributes": {k: v for k, v in event.attributes.items()}
                } for event in span.events
            ] if hasattr(span, "events") else [],
            "links": [
                {
                    "trace_id": format(link.context.trace_id, "032x"),
                    "span_id": format(link.context.span_id, "016x"),
                    "attributes": {k: v for k, v in link.attributes.items()}
                } for link in span.links
            ] if hasattr(span, "links") else []
        }
        
        # Save to file
        self._filesystem_spans.save_span(span_data)
