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

import os
from typing import Optional, List

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor, SpanProcessor

from llm_tracekit.instrumentation_utils import enable_capture_content


def setup_export_to_coralogix(
    service_name: str,
    coralogix_token: Optional[str] = None,
    coralogix_endpoint: Optional[str] = None,
    application_name: Optional[str] = None,
    subsystem_name: Optional[str] = None,
    use_batch_processor: bool = False,
    capture_content: bool = True,
    processors: Optional[List[SpanProcessor]] = None,
):
    """
    Setup OpenAI spans to be exported to Coralogix.

    Args:
        service_name: The service name.
        coralogix_token: The Coralogix token. Defaults to os.environ["CX_TOKEN"]
        coralogix_endpoint: The Coralogix endpoint. Defaults to os.environ["CX_ENDPOINT"]
        application_name: The Coralogix application name. Defaults to os.environ["CX_APPLICATION_NAME"]
        subsystem_name: The Coralogix subsystem name. Defaults to os.environ["CX_SUBSYSTEM_NAME"]
        use_batch_processor: Whether to use a batch processor or a simple processor.
        capture_content: Whether to capture the content of the messages.
        processors: Optional list of SpanProcessor instances to add to the tracer provider before the exporter processor.
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
        enable_capture_content()

    # set up a tracer provider to send spans to coralogix.
    tracer_provider = TracerProvider(
        resource=Resource.create({SERVICE_NAME: service_name}),
    )

    # add any custom span processors before configuring the exporter processor
    if processors:
        for span_processor in processors:
            tracer_provider.add_span_processor(span_processor)

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
