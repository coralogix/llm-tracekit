import httpx
import logging
from typing import List, Union, Optional, Any
from dotenv import load_dotenv
from tenacity import AsyncRetrying, stop_after_attempt, stop_after_delay, wait_exponential
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .models import GuardrailsRequest, GuardrailsResult, GuardrailsResponse, PII, PromptInjection, CustomGuardrail


logger = logging.getLogger(__name__)


class GuardrailsRequestConfig(BaseSettings):
    """Configuration settings for Guardrails with automatic environment variable loading."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="forbid"
    )
    
    api_key: str = Field(..., description="API key for authentication")
    application_name: str = Field(..., description="Name of the application")
    subsystem_name: str = Field(..., description="Name of the subsystem")
    domain_url: str = Field(..., description="Domain URL for the service")
    timeout: Union[int, str] = Field(default=100, ge=1, description="Request timeout in seconds")
    retries: Union[int, str] = Field(default=3, ge=0, description="Number of retry attempts")

    @field_validator('timeout', 'retries', mode='before')
    @classmethod
    def convert_to_int(cls, v):
        """Convert string or int to int."""
        if isinstance(v, str):
            return int(v.strip())
        return int(v)


    @field_validator('api_key', 'application_name', 'subsystem_name', 'domain_url')
    @classmethod
    def strip_whitespace_and_validate(cls, v: str) -> str:
        """Strip whitespace and ensure non-empty strings."""
        if not isinstance(v, str):
            raise ValueError("Must be a string")
        
        stripped = v.strip()
        if not stripped:
            raise ValueError("Cannot be empty or whitespace only")
        
        return stripped


class Guardrails:
    def __init__(self, 
                 api_key: Optional[Union[str, Any]] = None, 
                 application_name: Optional[Union[str, Any]] = None, 
                 subsystem_name: Optional[Union[str, Any]] = None, 
                 domain_url: Optional[Union[str, Any]] = None,
                 timeout: Union[int, str, Any] = 100, 
                 retries: Union[int, str, Any] = 3
                 ) -> None:

        load_dotenv()

        # Create config kwargs, only including non-None values
        config_kwargs = {}
        
        # Only add optional parameters if they're provided
        if api_key is not None:
            config_kwargs['api_key'] = str(api_key)
        if application_name is not None:
            config_kwargs['application_name'] = str(application_name)
        if subsystem_name is not None:
            config_kwargs['subsystem_name'] = str(subsystem_name)
        if domain_url is not None:
            config_kwargs['domain_url'] = str(domain_url)
        
        # Add numeric parameters with proper types
        config_kwargs['timeout'] = str(timeout)
        config_kwargs['retries'] = str(retries)

        # Initialize config with validation
        self.config = GuardrailsRequestConfig(**config_kwargs)
        
        # Expose config attributes at class level for backwards compatibility
        self.api_key = self.config.api_key
        self.application_name = self.config.application_name
        self.subsystem_name = self.config.subsystem_name
        self.domain_url = self.config.domain_url
        self.timeout = int(self.config.timeout)
        self.retries = int(self.config.retries)

        self._client = httpx.AsyncClient(
                base_url=self.domain_url, 
                # headers={"Authorization": f"Bearer {self.api_key}"}
                timeout=self.timeout,
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
                raise Exception(f"HTTP {response.status_code}: {response.text}")

            return response

    async def run(self, message: str, guardrails_config: List[Union[PII, PromptInjection, CustomGuardrail]]) -> List[GuardrailsResult]:
        guardrails_request = GuardrailsRequest(
            message=message, 
            guardrails_config=guardrails_config,
            api_key=self.api_key,
            application_name=self.application_name,
            subsystem_name=self.subsystem_name,
            domain_url=self.domain_url
        )

        

        logger.info(f"Running guardrails for message: {message}")
        logger.info(f"Guardrails config: {guardrails_request.guardrails_config}")

        async for attempt in AsyncRetrying(
            stop=(stop_after_attempt(self.retries) | stop_after_delay(self.timeout)), 
            wait=wait_exponential(),
            reraise=True
        ):
            with attempt:
                logger.info(f"Attempt {attempt.retry_state.attempt_number} of {self.retries}, for message: {message}")
                http_response = await self._run(guardrails_request)

        guardrails_response = GuardrailsResponse.model_validate_json(http_response.text)
        
        logger.info(f"HTTP response: {http_response.status_code} - {http_response.text}")        

        return guardrails_response.results
