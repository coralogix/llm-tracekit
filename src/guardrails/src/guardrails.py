import httpx
import logging
import os
from typing import List, Union, Optional
from dotenv import load_dotenv
from tenacity import AsyncRetrying, stop_after_attempt, stop_after_delay, wait_exponential
# from pydantic import Field, field_validator
# from pydantic_settings import BaseSettings

from .models import GuardrailsRequest, GuardrailsResult, GuardrailsResponse, PII, PromptInjection, CustomGuardrail


logger = logging.getLogger(__name__)


# class GuardrailsRequestConfig(BaseSettings):
#     api_key: str = Field(default=None, env="API_KEY")
#     application_name: str = Field(default=None, env="APPLICATION_NAME")
#     subsystem_name: str = Field(default=None, env="SUBSYSTEM_NAME")
#     domain_url: str = Field(default=None, env="DOMAIN_URL")
#     timeout: int = Field(default=10)
#     retries: int = Field(default=3)


#     @field_validator("api_key", "application_name", "subsystem_name", "domain_url")
#     @classmethod
#     def strip_whitespace(cls, v: str) -> str:
#         return v.strip() if isinstance(v, str) else v


class Guardrails:
    def __init__(self, 
        api_key: Optional[str] = None, 
        application_name: Optional[str] = None, 
        subsystem_name: Optional[str] = None, 
        domain_url: Optional[str] = None,
        timeout: int = 100, 
        retries: int = 3,
    ) -> None:
        load_dotenv()

        # Use environment variables as fallback if parameters not provided
        if api_key is None:
            api_key = os.getenv("API_KEY")
        if application_name is None:
            application_name = os.getenv("APPLICATION_NAME")
        if subsystem_name is None:
            subsystem_name = os.getenv("SUBSYSTEM_NAME")
        if domain_url is None:
            domain_url = os.getenv("DOMAIN_URL")
        
        # Strip whitespace and validate required parameters
        api_key = api_key.strip() if api_key else None
        application_name = application_name.strip() if application_name else None
        subsystem_name = subsystem_name.strip() if subsystem_name else None
        domain_url = domain_url.strip() if domain_url else None

        if not api_key:
            raise ValueError("api_key is required. Provide it as parameter or set API_KEY environment variable.")
        if not application_name:
            raise ValueError("application_name is required. Provide it as parameter or set APPLICATION_NAME environment variable.")
        if not subsystem_name:
            raise ValueError("subsystem_name is required. Provide it as parameter or set SUBSYSTEM_NAME environment variable.")
        if not domain_url:
            raise ValueError("domain_url is required. Provide it as parameter or set DOMAIN_URL environment variable.")
        
        self.api_key = api_key
        self.application_name = application_name
        self.subsystem_name = subsystem_name
        self.domain_url = domain_url
        self.timeout = timeout
        self.retries = retries

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
