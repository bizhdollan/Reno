import os
import re
from typing import AsyncGenerator, Optional, Any
import litellm
from litellm import acompletion

from src.config import get_llm_config, get_vlm_config, get_vgm_config, LLMConfig, VLMConfig, VGMConfig


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

    @classmethod
    def for_vgm(cls, **overrides) -> "LLMProvider":
        """Create provider for Vision Generation Model (image generation)."""
        config = get_vgm_config()
        return cls(
            provider=overrides.get("provider", config.provider),
            model=overrides.get("model", config.model),
            api_key=overrides.get("api_key", config.api_key)
        )

    async def generate_image(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any
    ) -> dict:
        """
        Generate an image using a vision generation model (e.g., Gemini 2.5 Flash Image).

        The model returns BOTH text description and image.

        Returns:
            dict with keys:
                - image_data: base64 decoded bytes
                - mime_type: str (e.g., 'image/png')
                - data_url: str (full data URL with base64 encoding)
                - description: str (text description of changes made)
        """
        self._validate_messages(messages)

        try:
            response = await acompletion(
                model=self.model,
                messages=messages,
                # Note: modalities param removed per test file
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
                **kwargs
            )

            choice = response.choices[0]

            # =====================================================================
            # EXTRACT TEXT DESCRIPTION
            # =====================================================================
            description = ""
            message_content = choice.message.content

            if isinstance(message_content, str):
                description = message_content
            else:
                # Content is a list of parts
                for part in message_content:
                    if hasattr(part, 'text') and part.text:
                        description = part.text
                        break

            print(f"[VGM] Extracted description: {description[:100]}..." if len(description) > 100 else f"[VGM] Extracted description: {description}")

            # =====================================================================
            # EXTRACT IMAGE - Check multiple locations
            # =====================================================================
            image_data = None
            mime_type = "image/png"
            image_data_url = None

            # Location 1: Native Gemini structure (most common)
            if hasattr(response, '_hidden_params') and 'candidates' in response._hidden_params:
                candidates = response._hidden_params['candidates']
                for candidate in candidates:
                    if 'content' in candidate and 'parts' in candidate['content']:
                        for part in candidate['content']['parts']:
                            # Check for inline_data (native Gemini format)
                            if isinstance(part, dict) and 'inline_data' in part:
                                import base64
                                image_data = base64.b64decode(part['inline_data']['data'])
                                mime_type = part['inline_data'].get('mime_type', 'image/png')
                                print(f"[VGM] Found image in native Gemini structure (inline_data)")
                                break
                            # Check for object with inline_data attribute
                            elif hasattr(part, 'inline_data') and part.inline_data:
                                import base64
                                image_data = base64.b64decode(part.inline_data.data)
                                mime_type = getattr(part.inline_data, 'mime_type', 'image/png')
                                print(f"[VGM] Found image in native Gemini structure (inline_data attr)")
                                break
                        if image_data:
                            break

            # Location 2: LiteLLM images array
            if not image_data and hasattr(choice.message, 'images') and choice.message.images:
                image_data_url = choice.message.images[0]["image_url"]["url"]

                # Parse the data URL
                # Format: data:image/png;base64,<base64_string>
                if image_data_url.startswith("data:"):
                    header, base64_string = image_data_url.split(",", 1)
                    mime_type = header.split(":")[1].split(";")[0]

                    import base64
                    image_data = base64.b64decode(base64_string)
                    print(f"[VGM] Found image in LiteLLM structure")
                else:
                    raise LLMProviderError(f"Unexpected image URL format: {image_data_url[:50]}")

            if not image_data:
                raise LLMProviderError("No image found in response. Checked both native Gemini and LiteLLM structures.")

            # Create data URL if not already present
            if not image_data_url:
                import base64
                base64_string = base64.b64encode(image_data).decode('utf-8')
                image_data_url = f"data:{mime_type};base64,{base64_string}"

            # Log token usage if available
            if hasattr(response, 'usage') and response.usage:
                print(f"[VGM Usage] Prompt tokens: {response.usage.prompt_tokens}, "
                      f"Completion tokens: {response.usage.completion_tokens}, "
                      f"Total: {response.usage.total_tokens}")

            return {
                "image_data": image_data,
                "mime_type": mime_type,
                "data_url": image_data_url,
                "description": description
            }

        except Exception as e:
            raise LLMProviderError(f"Image generation failed: {str(e)}") from e
