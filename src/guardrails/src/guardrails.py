import httpx
import logging
from typing import List, Union, Annotated
from tenacity import AsyncRetrying, stop_after_attempt, stop_after_delay, wait_exponential
from pydantic import Field, StringConstraints
from pydantic_settings import BaseSettings, SettingsConfigDict

from .models import GuardrailsRequest, GuardrailsResult, GuardrailsResponse, PII, PromptInjection, CustomGuardrail
from .error import GuardrailsAPIResponseError


logger = logging.getLogger(__name__)

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]



class GuardrailsRequestConfig(BaseSettings):
    """Configuration settings for Guardrails with automatic environment variable loading."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="forbid"
    )
    
    api_key: NonEmptyStr = Field(..., description="API key for authentication")
    application_name: NonEmptyStr = Field(..., description="Name of the application")
    subsystem_name: NonEmptyStr = Field(..., description="Name of the subsystem")
    domain_url: NonEmptyStr = Field(..., description="Domain URL for the service")
    timeout: int = Field(default=100, ge=1, description="Request timeout in seconds")
    retries: int = Field(default=3, ge=0, description="Number of retry attempts")


class Guardrails:
    def __init__(self, 
                 api_key: str | None = None, 
                 application_name: str | None = None, 
                 subsystem_name: str | None = None, 
                 domain_url: str | None = None, 
                 timeout: int | None = None, 
                 retries: int | None = None,
                 ) -> None:


        local_vars = locals().copy()
        print("Local vars: \n", local_vars)
        # Create config kwargs, only including non-None values
        config_kwargs = {k: v for k, v in local_vars.items() if v is not None}
        config_kwargs.pop("self", None)

        # Initialize config with validation
        self.config = GuardrailsRequestConfig(**config_kwargs)

        self._client = httpx.AsyncClient(
                base_url=self.config.domain_url, 
                # headers={"Authorization": f"Bearer {self.config.api_key}"}
                timeout=self.config.timeout,
    )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self): 
        print("Entering guardrails context")
        return self

    async def __aexit__(self, *_): 
        print("Exiting guardrails context")
        await self.aclose()

    async def _run(self, guardrails_request: GuardrailsRequest) -> httpx.Response:
            guardrails_json_request = guardrails_request.model_dump()
            guardrails_json_request["guardrails_config"] = [g.model_dump() for g in guardrails_request.guardrails_config]
            
            logger.debug(f"Sending request payload: {guardrails_json_request}")

            response = await self._client.post(
                "/guardrails/run",
                json=guardrails_json_request
            )

            logger.debug(f"Received response with status code:{response.status_code}")
            logger.debug(f"Response text: {response.text}")

    

            if response.status_code >= 400:
                logger.error(f"Received error response: {response.text}")
                raise GuardrailsAPIResponseError(response.status_code, response.text)

            return response

    async def run(self, message: str, guardrails_config: List[Union[PII, PromptInjection, CustomGuardrail]]) -> List[GuardrailsResult]:
        guardrails_request = GuardrailsRequest(
            message=message, 
            guardrails_config=guardrails_config,
            api_key=self.config.api_key,
            application_name=self.config.application_name,
            subsystem_name=self.config.subsystem_name,
            domain_url=self.config.domain_url
        )

        logger.info(f"Running guardrails for message: {message}")
        logger.info(f"Guardrails config: {guardrails_request.guardrails_config}")

        async for attempt in AsyncRetrying(
            stop=(stop_after_attempt(self.config.retries) | stop_after_delay(self.config.timeout)), 
            wait=wait_exponential(),
            reraise=True
        ):
            with attempt:
                logger.info(f"Attempt {attempt.retry_state.attempt_number} of {self.config.retries}, for message: {message}")
                http_response = await self._run(guardrails_request)

        guardrails_response = GuardrailsResponse.model_validate_json(http_response.text)
        
        logger.info(f"HTTP response: {http_response.status_code} - {http_response.text}")        

        return guardrails_response.results
