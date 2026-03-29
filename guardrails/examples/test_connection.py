"""Test connectivity to the Guardrails API before running guardrail checks."""

import asyncio
import sys
from cx_guardrails import (
    Guardrails,
    GuardrailsAPIConnectionError,
    GuardrailsAPITimeoutError,
    GuardrailsAPIResponseError,
    setup_export_to_coralogix,
)

setup_export_to_coralogix(service_name="guardrails-connection-test")
guardrails = Guardrails(
    application_name="my_application", subsystem_name="my_subsystem"
)


async def main():
    print("Testing connection to the Guardrails API...")

    try:
        response = await guardrails.test_connection()
        print(f"Connection successful. Received {len(response.results)} result(s).")
    except GuardrailsAPIConnectionError as e:
        print(f"Connection failed — check your endpoint and network: {e}")
        sys.exit(1)
    except GuardrailsAPITimeoutError as e:
        print(f"Request timed out — the API may be overloaded or unreachable: {e}")
        sys.exit(1)
    except GuardrailsAPIResponseError as e:
        print(f"API returned an error (HTTP {e.status_code}): {e.message}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
