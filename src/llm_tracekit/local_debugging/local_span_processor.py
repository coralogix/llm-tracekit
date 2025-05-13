from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanProcessor
from llm_tracekit.local_debugging.local_span_exporter import LocalSpanExporter


class LocalSpanProcessor(SpanProcessor):
    """A span processor that exports spans to a local file for debugging.
    
    This processor collects and forwards spans to the LocalSpanExporter, which
    writes them to the local filesystem for debugging purposes.
    """
    
    def __init__(self, traces_directory: str | None):
        """Initialize the local debug span processor.
        
        Args:
            exporter: The span exporter to use. Defaults to LocalSpanExporter.
        """
        self._exporter = LocalSpanExporter(traces_directory)
    
    def on_start(self, span, parent_context=None):
        """Called when a span starts.
        
        Args:
            span: The span that started.
            parent_context: The parent context of the span.
        """
        pass
    
    def on_end(self, span):
        """Called when a span ends.
        
        Args:
            span: The span that ended.
        """
        if isinstance(span, ReadableSpan):
            self._exporter.export(span)
    
    def shutdown(self):
        """Shuts down the processor."""
        pass
    
    def force_flush(self, timeout_millis=30000):
        """Forces a flush of spans.
        
        Args:
            timeout_millis: The maximum amount of time to wait for the flush to complete.
        
        Returns:
            True if the flush was successful, False otherwise.
        """
        return True
