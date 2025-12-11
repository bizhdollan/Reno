import os
import re
from typing import AsyncGenerator, Optional, Any
import litellm
from litellm import acompletion

from src.config import get_llm_config, get_vlm_config, LLMConfig, VLMConfig


# supported image formats across all providers (openai, anthropic, gemini)
SUPPORTED_IMAGE_FORMATS = ["image/jpeg", "image/png", "image/webp"]


class UnsupportedImageFormatError(ValueError):
    pass


class LLMProviderError(Exception):
    pass


class LLMProvider:
    """
    Unified LLM provider using LiteLLM for OpenAI, Anthropic, and Gemini models.
    
    Supports:
    - Text-only and multimodal (text + base64 images) completions
    - Streaming and non-streaming responses
    
    Example:
        provider = LLMProvider()
        response = await provider.complete([
            {"role": "user", "content": "Hello!"}
        ])
    """
    
    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        if provider is None or model is None or api_key is None:
            config = get_llm_config()
            self.provider = provider or config.provider
            self.model = model or config.model
            self.api_key = api_key or config.api_key
        else:
            self.provider = provider
            self.model = model
            self.api_key = api_key
        
        self._set_api_key_env()
    
    def _set_api_key_env(self) -> None:
        provider_lower = self.provider.lower()
        
        if provider_lower == "openai":
            os.environ["OPENAI_API_KEY"] = self.api_key
        elif provider_lower == "anthropic":
            os.environ["ANTHROPIC_API_KEY"] = self.api_key
        elif provider_lower in ["gemini", "google"]:
            os.environ["GOOGLE_API_KEY"] = self.api_key
        else:
            os.environ["LLM_API_KEY"] = self.api_key
    
    def _validate_messages(self, messages: list[dict]) -> None:
        for message in messages:
            content = message.get("content")
            
            # check if content is a list (multimodal)
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "image_url":
                        image_url = item.get("image_url", {}).get("url", "")
                        self._validate_image_format(image_url)
    
    def _validate_image_format(self, image_url: str) -> None:
        if not image_url.startswith("data:"):
            raise UnsupportedImageFormatError(
                "Image must be provided as a data URL (data:image/...;base64,...)"
            )
        
        # Extract MIME type from data URL
        # Format: data:image/jpeg;base64,<base64_data>
        match = re.match(r"data:(image/[^;]+);", image_url)
        if not match:
            raise UnsupportedImageFormatError(
                "Invalid data URL format. Expected: data:image/...;base64,..."
            )
        
        mime_type = match.group(1)
        
        if mime_type not in SUPPORTED_IMAGE_FORMATS:
            raise UnsupportedImageFormatError(
                f"Unsupported image format: {mime_type}. "
                f"Supported formats: {', '.join(SUPPORTED_IMAGE_FORMATS)}"
            )
    
    async def complete(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs: Any
    ) -> str:
        self._validate_messages(messages)
        
        try:
            response = await acompletion(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
                **kwargs
            )
            
            # Extract the completion text
            content = response.choices[0].message.content
            
            # Log token usage if available
            if hasattr(response, 'usage') and response.usage:
                print(f"[LLM Usage] Prompt tokens: {response.usage.prompt_tokens}, "
                      f"Completion tokens: {response.usage.completion_tokens}, "
                      f"Total: {response.usage.total_tokens}")
            
            return content
            
        except Exception as e:
            raise LLMProviderError(f"LLM completion failed: {str(e)}") from e
    
    async def complete_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        self._validate_messages(messages)
        
        try:
            response = await acompletion(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                **kwargs
            )
            
            # Stream the chunks
            async for chunk in response:
                # Extract delta content
                if hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'content'):
                    content = chunk.choices[0].delta.content
                    if content:
                        yield content
                        
        except Exception as e:
            raise LLMProviderError(f"LLM streaming completion failed: {str(e)}") from e
    
    async def complete_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs: Any
    ):
        self._validate_messages(messages)

        try:
            response = await acompletion(
                model=self.model,
                messages=messages,
                tools=tools,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
                **kwargs
            )
            if hasattr(response, 'usage') and response.usage:
                print(f"[LLM Usage] Prompt tokens: {response.usage.prompt_tokens}, "
                      f"Completion tokens: {response.usage.completion_tokens}, "
                      f"Total: {response.usage.total_tokens}")
            return response
        except Exception as e:
            raise LLMProviderError(f"LLM completion with tools failed: {str(e)}") from e

    @classmethod
    def for_llm(cls, **overrides) -> "LLMProvider":
        config = get_llm_config()
        return cls(
            provider=overrides.get("provider", config.provider),
            model=overrides.get("model", config.model),
            api_key=overrides.get("api_key", config.api_key)
        )
    
    @classmethod
    def for_vlm(cls, **overrides) -> "LLMProvider":
        config = get_vlm_config()
        return cls(
            provider=overrides.get("provider", config.provider),
            model=overrides.get("model", config.model),
            api_key=overrides.get("api_key", config.api_key)
        )
