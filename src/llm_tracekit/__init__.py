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

from contextlib import suppress

from llm_tracekit.coralogix import (
    setup_export_to_coralogix as setup_export_to_coralogix,
)

with suppress(ImportError):
    from llm_tracekit.openai.instrumentor import (
        OpenAIInstrumentor as OpenAIInstrumentor,
    )

with suppress(ImportError):
    from llm_tracekit.bedrock.instrumentor import (
        BedrockInstrumentor as BedrockInstrumentor,
    )
