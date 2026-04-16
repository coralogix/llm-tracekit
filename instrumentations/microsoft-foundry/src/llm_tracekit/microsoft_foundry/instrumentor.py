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


from typing import Collection
import weakref

from opentelemetry.instrumentation.instrumentor import (  # type: ignore[attr-defined]
    BaseInstrumentor,
)
from opentelemetry.instrumentation.utils import unwrap
from opentelemetry.metrics import get_meter
from opentelemetry.semconv.schemas import Schemas
from opentelemetry.trace import get_tracer
from wrapt import wrap_function_wrapper

from llm_tracekit.core import is_content_enabled, Instruments
from llm_tracekit.microsoft_foundry.package import _instruments
from llm_tracekit.microsoft_foundry.patch import (
    chat_completions_create,
    async_chat_completions_create,
    responses_create,
    async_responses_create,
    embeddings_create,
    async_embeddings_create,
)

_INSTRUMENTED_CLIENTS: weakref.WeakSet = weakref.WeakSet()


class MicrosoftFoundryInstrumentor(BaseInstrumentor):
    def __init__(self):
        self._meter = None
        self._tracer = None
        self._instruments = None
        self._capture_content = False

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs):
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

        self._instruments = Instruments(self._meter)
        self._capture_content = is_content_enabled()

        wrap_function_wrapper(
            module="azure.ai.projects",
            name="AIProjectClient.get_openai_client",
            wrapper=self._wrap_get_openai_client(),
        )

        try:
            wrap_function_wrapper(
                module="azure.ai.projects.aio",
                name="AIProjectClient.get_openai_client",
                wrapper=self._wrap_async_get_openai_client(),
            )
        except (ImportError, AttributeError):
            pass

    def _uninstrument(self, **kwargs):
        try:
            import azure.ai.projects

            unwrap(azure.ai.projects.AIProjectClient, "get_openai_client")
        except (ImportError, AttributeError):
            pass

        try:
            import azure.ai.projects.aio

            unwrap(azure.ai.projects.aio.AIProjectClient, "get_openai_client")
        except (ImportError, AttributeError):
            pass

        _INSTRUMENTED_CLIENTS.clear()

    def _wrap_get_openai_client(self):
        """Wrap sync get_openai_client to instrument the returned OpenAI client."""
        instrumentor = self

        def wrapper(wrapped, instance, args, kwargs):
            client = wrapped(*args, **kwargs)
            instrumentor._instrument_openai_client(client)
            return client

        return wrapper

    def _wrap_async_get_openai_client(self):
        """Wrap async get_openai_client to instrument the returned OpenAI client."""
        instrumentor = self

        def wrapper(wrapped, instance, args, kwargs):
            client = wrapped(*args, **kwargs)
            instrumentor._instrument_openai_client(client, is_async=True)
            return client

        return wrapper

    def _instrument_openai_client(self, client, is_async: bool = False):
        """Instrument an OpenAI client instance's methods."""
        if client in _INSTRUMENTED_CLIENTS:
            return

        _INSTRUMENTED_CLIENTS.add(client)

        tracer = self._tracer
        instruments = self._instruments
        capture_content = self._capture_content

        if is_async:
            self._wrap_async_client_methods(
                client, tracer, instruments, capture_content
            )
        else:
            self._wrap_sync_client_methods(client, tracer, instruments, capture_content)

    def _wrap_sync_client_methods(self, client, tracer, instruments, capture_content):
        """Wrap sync OpenAI client methods."""
        if hasattr(client, "chat") and hasattr(client.chat, "completions"):
            original_chat_create = client.chat.completions.create
            chat_wrapper = chat_completions_create(tracer, instruments, capture_content)

            def wrapped_chat_create(
                *args,
                _orig=original_chat_create,
                _wrap=chat_wrapper,
                _inst=client.chat.completions,
                **kwargs,
            ):
                return _wrap(_orig, _inst, args, kwargs)

            client.chat.completions.create = wrapped_chat_create

        if hasattr(client, "responses"):
            original_responses_create = client.responses.create
            responses_wrapper = responses_create(tracer, instruments, capture_content)

            def wrapped_responses_create(
                *args,
                _orig=original_responses_create,
                _wrap=responses_wrapper,
                _inst=client.responses,
                **kwargs,
            ):
                return _wrap(_orig, _inst, args, kwargs)

            client.responses.create = wrapped_responses_create

        if hasattr(client, "embeddings"):
            original_embeddings_create = client.embeddings.create
            embeddings_wrapper = embeddings_create(tracer, instruments, capture_content)

            def wrapped_embeddings_create(
                *args,
                _orig=original_embeddings_create,
                _wrap=embeddings_wrapper,
                _inst=client.embeddings,
                **kwargs,
            ):
                return _wrap(_orig, _inst, args, kwargs)

            client.embeddings.create = wrapped_embeddings_create

    def _wrap_async_client_methods(self, client, tracer, instruments, capture_content):
        """Wrap async OpenAI client methods."""
        if hasattr(client, "chat") and hasattr(client.chat, "completions"):
            original_chat_create = client.chat.completions.create
            chat_wrapper = async_chat_completions_create(
                tracer, instruments, capture_content
            )

            async def wrapped_chat_create(
                *args,
                _orig=original_chat_create,
                _wrap=chat_wrapper,
                _inst=client.chat.completions,
                **kwargs,
            ):
                return await _wrap(_orig, _inst, args, kwargs)

            client.chat.completions.create = wrapped_chat_create

        if hasattr(client, "responses"):
            original_responses_create = client.responses.create
            responses_wrapper = async_responses_create(
                tracer, instruments, capture_content
            )

            async def wrapped_responses_create(
                *args,
                _orig=original_responses_create,
                _wrap=responses_wrapper,
                _inst=client.responses,
                **kwargs,
            ):
                return await _wrap(_orig, _inst, args, kwargs)

            client.responses.create = wrapped_responses_create

        if hasattr(client, "embeddings"):
            original_embeddings_create = client.embeddings.create
            embeddings_wrapper = async_embeddings_create(
                tracer, instruments, capture_content
            )

            async def wrapped_embeddings_create(
                *args,
                _orig=original_embeddings_create,
                _wrap=embeddings_wrapper,
                _inst=client.embeddings,
                **kwargs,
            ):
                return await _wrap(_orig, _inst, args, kwargs)

            client.embeddings.create = wrapped_embeddings_create
