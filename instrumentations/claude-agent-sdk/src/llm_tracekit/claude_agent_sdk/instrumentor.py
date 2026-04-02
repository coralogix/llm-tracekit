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
from opentelemetry.semconv.schemas import Schemas
from opentelemetry.trace import get_tracer

from llm_tracekit.core import is_content_enabled
from llm_tracekit.claude_agent_sdk.package import _instruments
from llm_tracekit.claude_agent_sdk.patch import (
    create_wrapped_client_query,
    create_wrapped_query,
    create_wrapped_receive_response,
)


class ClaudeAgentSDKInstrumentor(BaseInstrumentor):
    """Instrumentor for Claude Agent SDK that traces query() and ClaudeSDKClient."""

    _original_query: Any = None
    _original_client_query: Any = None
    _original_receive_response: Any = None
    _query_module: ModuleType | None = None
    _main_module: ModuleType | None = None
    _client_class: type[Any] | None = None

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
        capture_content = is_content_enabled()

        # Patch both the submodule and the package-level re-export so that
        # `from claude_agent_sdk import query` and `from claude_agent_sdk.query import query`
        # both receive the instrumented version.
        query_module = importlib.import_module("claude_agent_sdk.query")
        main_module = importlib.import_module("claude_agent_sdk")
        from claude_agent_sdk.client import ClaudeSDKClient

        ClaudeAgentSDKInstrumentor._query_module = query_module
        ClaudeAgentSDKInstrumentor._main_module = main_module
        ClaudeAgentSDKInstrumentor._client_class = ClaudeSDKClient
        ClaudeAgentSDKInstrumentor._original_query = getattr(query_module, "query")
        ClaudeAgentSDKInstrumentor._original_client_query = ClaudeSDKClient.query
        ClaudeAgentSDKInstrumentor._original_receive_response = ClaudeSDKClient.receive_response

        cls = ClaudeAgentSDKInstrumentor
        wrapped_query = create_wrapped_query(cls._original_query, tracer, capture_content)
        setattr(query_module, "query", wrapped_query)
        if hasattr(main_module, "query"):
            setattr(main_module, "query", wrapped_query)
        setattr(
            ClaudeSDKClient,
            "query",
            create_wrapped_client_query(cls._original_client_query),
        )
        setattr(
            ClaudeSDKClient,
            "receive_response",
            create_wrapped_receive_response(cls._original_receive_response, tracer, capture_content),
        )

    def _uninstrument(self, **kwargs) -> None:
        cls = ClaudeAgentSDKInstrumentor
        if cls._query_module is not None and cls._original_query is not None:
            setattr(cls._query_module, "query", cls._original_query)
        if cls._main_module is not None and cls._original_query is not None:
            if hasattr(cls._main_module, "query"):
                setattr(cls._main_module, "query", cls._original_query)
        if cls._client_class is not None:
            if cls._original_client_query is not None:
                setattr(cls._client_class, "query", cls._original_client_query)
            if cls._original_receive_response is not None:
                setattr(
                    cls._client_class,
                    "receive_response",
                    cls._original_receive_response,
                )
        cls._original_query = None
        cls._original_client_query = None
        cls._original_receive_response = None
        cls._query_module = None
        cls._main_module = None
        cls._client_class = None
