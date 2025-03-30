# Copyright The OpenTelemetry Authors
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

"""
OpenAI client instrumentation supporting `openai`, it can be enabled by
using ``OpenAIInstrumentor``.

.. _openai: https://pypi.org/project/openai/

Usage
-----

.. code:: python

    from openai import OpenAI
    from llm_tracekit import OpenAIInstrumentor

    OpenAIInstrumentor().instrument()

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": "Write a short poem on open telemetry."},
        ],
    )

API
---
"""

import os
from typing import Collection, Optional

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.instrumentor import (  # type: ignore[attr-defined] # Mypy doesn't recognize the attribute
    BaseInstrumentor,
)
from opentelemetry.instrumentation.utils import unwrap
from opentelemetry.metrics import get_meter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
from opentelemetry.semconv.schemas import Schemas
from opentelemetry.trace import get_tracer
from wrapt import wrap_function_wrapper

from llm_tracekit.package import _instruments
from llm_tracekit.utils import is_content_enabled

from .instruments import Instruments
from .patch import async_chat_completions_create, chat_completions_create
from .utils import OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT


class OpenAIInstrumentor(BaseInstrumentor):
    def __init__(self):
        self._meter = None

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs):
        """Enable OpenAI instrumentation."""
        tracer_provider = kwargs.get("tracer_provider")
        tracer = get_tracer(
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

        wrap_function_wrapper(
            module="openai.resources.chat.completions",
            name="Completions.create",
            wrapper=chat_completions_create(tracer, instruments, is_content_enabled()),
        )

        wrap_function_wrapper(
            module="openai.resources.chat.completions",
            name="AsyncCompletions.create",
            wrapper=async_chat_completions_create(
                tracer, instruments, is_content_enabled()
            ),
        )

    def _uninstrument(self, **kwargs):
        import openai  # pylint: disable=import-outside-toplevel

        unwrap(openai.resources.chat.completions.Completions, "create")
        unwrap(openai.resources.chat.completions.AsyncCompletions, "create")


def setup_export_to_coralogix(
    service_name: str,
    coralogix_token: Optional[str] = None,
    coralogix_endpoint: Optional[str] = None,
    application_name: Optional[str] = None,
    subsystem_name: Optional[str] = None,
    use_batch_processor: bool = False,
    capture_content: bool = True,
):
    """
    Setup OpenAI spans to be exported to Coralogix.

    Args:
        service_name: The service name.
        coralogix_token: The Coralogix token. Defaults to os.environ["CX_TOKEN]
        coralogix_endpoint: The Coralogix endpoint. Defaults to os.environ["CX_ENDPOINT"]
        application_name: The Coralogix application name. Defaults to os.environ["CX_APPLICATION_NAME"]
        subsystem_name: The Coralogix subsystem name. Defaults to os.environ["CX_SUBSYSTEM_NAME"]
        use_batch_processor: Whether to use a batch processor or a simple processor..
        capture_content: Whether to capture the content of the messages.
    """

    # Read environment variables as defaults if needed
    if coralogix_token is None:
        coralogix_token = os.environ["CX_TOKEN"]
    if coralogix_endpoint is None:
        coralogix_endpoint = os.environ["CX_ENDPOINT"]
    if application_name is None:
        application_name = os.environ["CX_APPLICATION_NAME"]
    if subsystem_name is None:
        subsystem_name = os.environ["CX_SUBSYSTEM_NAME"]
    if capture_content:
        os.environ[OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT] = "true"

    # set up a tracer provider to send spans to coralogix.
    tracer_provider = TracerProvider(
        resource=Resource.create({SERVICE_NAME: service_name}),
    )

    # set up an OTLP exporter to send spans to coralogix directly.
    headers = {
        "authorization": f"Bearer {coralogix_token}",
        "cx-application-name": application_name,
        "cx-subsystem-name": subsystem_name,
    }
    exporter = OTLPSpanExporter(endpoint=coralogix_endpoint, headers=headers)

    # set up a span processor to send spans to the exporter
    span_processor = (
        BatchSpanProcessor(exporter)
        if use_batch_processor
        else SimpleSpanProcessor(exporter)
    )

    # add the span processor to the tracer provider
    tracer_provider.add_span_processor(span_processor)
    trace.set_tracer_provider(tracer_provider)
