# Copyright Coralogix Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Instrumentor for Claude Agent SDK."""

from collections.abc import Collection
from types import ModuleType
from typing import Any

from opentelemetry.instrumentation.instrumentor import (  # type: ignore[attr-defined]
    BaseInstrumentor,
)
from opentelemetry.metrics import get_meter
from opentelemetry.semconv.schemas import Schemas
from opentelemetry.trace import get_tracer

from llm_tracekit.core import is_content_enabled
from llm_tracekit.core._metrics import Instruments
from llm_tracekit.claude_agent_sdk.package import _instruments
from llm_tracekit.claude_agent_sdk.patch import (
    create_wrapped_client_query,
    create_wrapped_query,
    create_wrapped_receive_response,
)


class ClaudeAgentSDKInstrumentor(BaseInstrumentor):
    """Instrumentor for Claude Agent SDK that traces query() and ClaudeSDKClient."""

    def __init__(self):
        super().__init__()
        self._original_query: Any = None
        self._original_client_query: Any = None
        self._original_receive_response: Any = None
        self._query_module: ModuleType | None = None
        self._main_module: ModuleType | None = None
        self._client_class: type[Any] | None = None

    def instrumentation_dependencies(self) -> Collection[str]:  # type: ignore[override]
        return _instruments

    def _instrument(self, **kwargs) -> None:
        import importlib

        tracer_provider = kwargs.get("tracer_provider")
        tracer = get_tracer(
            __name__,
            "",
            tracer_provider,
            schema_url=Schemas.V1_28_0.value,
        )
        meter_provider = kwargs.get("meter_provider")
        meter = get_meter(
            __name__,
            "",
            meter_provider,
            schema_url=Schemas.V1_28_0.value,
        )
        instruments = Instruments(meter)
        capture_content = is_content_enabled()

        # Patch both the submodule and the package-level re-export so that
        # `from claude_agent_sdk import query` and `from claude_agent_sdk.query import query`
        # both receive the instrumented version.
        query_module = importlib.import_module("claude_agent_sdk.query")
        main_module = importlib.import_module("claude_agent_sdk")
        from claude_agent_sdk.client import ClaudeSDKClient

        self._query_module = query_module
        self._main_module = main_module
        self._client_class = ClaudeSDKClient
        self._original_query = getattr(query_module, "query")
        self._original_client_query = ClaudeSDKClient.query
        self._original_receive_response = ClaudeSDKClient.receive_response

        wrapped_query = create_wrapped_query(
            self._original_query, tracer, instruments, capture_content
        )
        setattr(query_module, "query", wrapped_query)
        if hasattr(main_module, "query"):
            setattr(main_module, "query", wrapped_query)
        setattr(
            ClaudeSDKClient,
            "query",
            create_wrapped_client_query(self._original_client_query),
        )
        setattr(
            ClaudeSDKClient,
            "receive_response",
            create_wrapped_receive_response(
                self._original_receive_response, tracer, instruments, capture_content
            ),
        )

    def _uninstrument(self, **kwargs) -> None:
        if self._query_module is not None and self._original_query is not None:
            setattr(self._query_module, "query", self._original_query)
        if self._main_module is not None and self._original_query is not None:
            if hasattr(self._main_module, "query"):
                setattr(self._main_module, "query", self._original_query)
        if self._client_class is not None:
            if self._original_client_query is not None:
                setattr(self._client_class, "query", self._original_client_query)
            if self._original_receive_response is not None:
                setattr(
                    self._client_class,
                    "receive_response",
                    self._original_receive_response,
                )
        self._original_query = None
        self._original_client_query = None
        self._original_receive_response = None
        self._query_module = None
        self._main_module = None
        self._client_class = None
