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

from __future__ import annotations

from typing import Any, Callable, Collection

from langchain_core.callbacks import BaseCallbackManager  # type: ignore
from opentelemetry.instrumentation.instrumentor import (  # type: ignore[attr-defined]
    BaseInstrumentor,
)
from opentelemetry.instrumentation.utils import unwrap
from opentelemetry.metrics import Meter, get_meter
from opentelemetry.semconv.schemas import Schemas
from opentelemetry.trace import Tracer, get_tracer
from wrapt import wrap_function_wrapper

from llm_tracekit.instrumentation_utils import is_content_enabled
from llm_tracekit.instruments import Instruments
from llm_tracekit.langchain.callback import LangChainCallbackHandler
from llm_tracekit.langchain.package import _instruments


class LangChainInstrumentor(BaseInstrumentor):
    def __init__(self) -> None:
        self._meter: Meter | None = None
        self._tracer: Tracer | None = None
        self._handler: LangChainCallbackHandler | None = None

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs: Any) -> None:
        tracer_provider = kwargs.get("tracer_provider")
        self._tracer = get_tracer(
            __name__,
            "",
            tracer_provider,
            schema_url=Schemas.V1_28_0.value,
        )

        meter_provider = kwargs.get("meter_provider")
        self._meter = get_meter(
            __name__,
            "",
            meter_provider,
            schema_url=Schemas.V1_28_0.value,
        )

        instruments = Instruments(self._meter)
        capture_content = is_content_enabled()
        self._handler = LangChainCallbackHandler(
            tracer=self._tracer,
            instruments=instruments,
            capture_content=capture_content,
        )

        wrap_function_wrapper(
            module="langchain_core.callbacks",
            name="BaseCallbackManager.__init__",
            wrapper=_BaseCallbackManagerInitWrapper(lambda: self._handler),
        )

    def _uninstrument(self, **kwargs: Any) -> None:
        unwrap("langchain_core.callbacks.base.BaseCallbackManager", "__init__")


class _BaseCallbackManagerInitWrapper:
    def __init__(self, handler_factory: Callable[[], LangChainCallbackHandler | None]) -> None:
        self._handler_factory = handler_factory

    def __call__(
        self,
        wrapped: Callable[..., None],
        instance: BaseCallbackManager,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> None:
        wrapped(*args, **kwargs)

        handler = self._handler_factory()
        if handler is None:
            return

        for existing_handler in instance.inheritable_handlers:  # type: ignore[attr-defined]
            if isinstance(existing_handler, type(handler)):
                return

        instance.add_handler(handler, inherit=True)  # type: ignore[attr-defined]
