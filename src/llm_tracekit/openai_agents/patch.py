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

import wrapt

from agents import Runner
from opentelemetry.context import attach, detach, set_value


async def runner_run_wrapper(wrapped, instance, args, kwargs):
    """Wrapper for Runner.run to extract invocation_id."""
    # Extract invocation_id if present
    invocation_id = kwargs.pop("invocation_id", None)
    
    # Set invocation_id in context if provided
    context_token = None
    if invocation_id is not None:
        context_token = attach(set_value("llm_tracekit.invocation_id", invocation_id))
    
    try:
        # Call the original Runner.run (it's async)
        result = await wrapped(*args, **kwargs)
        return result
    finally:
        # Clean up context
        if context_token is not None:
            detach(context_token)


def patch_runner_run():
    """Patch Runner.run to extract invocation_id."""
    wrapt.wrap_function_wrapper(
        Runner,
        "run",
        runner_run_wrapper
    )


__all__ = ["patch_runner_run"]

