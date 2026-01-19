import os
import re
from typing import AsyncGenerator, Optional, Any
from uuid import uuid4
import litellm
from litellm import acompletion

from src.core.logger import get_logger
from src.config import get_llm_config, get_vlm_config, get_vgm_config, LLMConfig, VLMConfig, VGMConfig

logger = get_logger(__name__)


# supported image formats across all providers (openai, anthropic, gemini)
SUPPORTED_IMAGE_FORMATS = ["image/jpeg", "image/png", "image/webp"]

# Reasoning models that don't support custom temperature
# These models only support temperature=1 (or no temperature param)
REASONING_MODELS = [
    "gpt-5",
    "gpt-5-codex",
    "o1",
    "o1-mini",
    "o1-preview",
    "o3",
    "o3-mini",
]


def is_reasoning_model(model_name: str) -> bool:
    """Check if the model is a reasoning model that doesn't support custom temperature."""
    model_lower = model_name.lower()
    return any(reasoning in model_lower for reasoning in REASONING_MODELS)


# =============================================================================
# PRICING CONFIGURATION (per 1M tokens)
# =============================================================================
MODEL_PRICING = {
    # OpenAI
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-vision-preview": {"input": 10.00, "output": 30.00},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-4": {"input": 30.00, "output": 60.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},

    # Anthropic
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    "claude-3-sonnet-20240229": {"input": 3.00, "output": 15.00},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},

    # Google Gemini
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-2.0-flash-exp": {"input": 0.075, "output": 0.30},
    "gemini-2.5-flash": {"input": 0.075, "output": 0.30},
    "gemini/gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    "gemini/gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini/gemini-2.0-flash-exp": {"input": 0.075, "output": 0.30},
    "gemini/gemini-2.5-flash-preview-05-20": {"input": 0.075, "output": 0.30},

    # Default fallback
    "default": {"input": 1.00, "output": 2.00},
}


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

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate cost in USD for an API call.

        Args:
            input_tokens: Number of input/prompt tokens
            output_tokens: Number of output/completion tokens

        Returns:
            Cost in USD (with 6 decimal precision)
        """
        # Get pricing for this model
        pricing = MODEL_PRICING.get(self.model, MODEL_PRICING.get("default"))

        # Calculate cost (pricing is per 1M tokens)
        input_cost = (input_tokens * pricing["input"]) / 1_000_000
        output_cost = (output_tokens * pricing["output"]) / 1_000_000
        total_cost = round(input_cost + output_cost, 6)

        return total_cost

    def _safe_uuid(self, value: Optional[str]) -> Optional["UUID"]:
        """
        Safely convert a string to UUID.

        Returns None if:
        - value is None or empty
        - value is not a valid UUID format (e.g., project tokens like PRJ-XXXXX)

        Args:
            value: String that might be a UUID

        Returns:
            UUID object if valid, None otherwise
        """
        if not value:
            return None

        from uuid import UUID

        # Check if it looks like a UUID (has dashes in right places or is 32 hex chars)
        # UUID format: 8-4-4-4-12 (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)
        try:
            return UUID(value)
        except (ValueError, AttributeError):
            # Not a valid UUID format (e.g., project token like PRJ-10NKXQ)
            return None

    async def _log_cost(
        self,
        api_call_id: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        operation_type: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> None:
        """
        Log LLM cost to database.

        This is a best-effort logging - failures don't break the main flow.

        Note: project_id can be either a UUID string or a project token (PRJ-XXXXX).
        Only valid UUIDs will be stored; tokens will result in project_id=None.
        """
        try:
            from src.db.database import SessionLocal
            from src.db.models import LLMCost

            # Safely convert to UUIDs - handles tokens like PRJ-XXXXX gracefully
            api_call_uuid = self._safe_uuid(api_call_id)
            project_uuid = self._safe_uuid(project_id)

            db = SessionLocal()
            try:
                cost_record = LLMCost(
                    api_call_id=api_call_uuid,
                    project_id=project_uuid,
                    model=self.model,
                    operation_type=operation_type,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost=cost_usd,  # Legacy column
                    cost_usd=cost_usd  # New precise column
                )
                db.add(cost_record)
                db.commit()
            finally:
                db.close()
        except Exception as e:
            # Log but don't fail
            logger.warning(f"[LLM Cost Tracking] Failed to log cost: {e}")
    
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
        operation_type: Optional[str] = None,
        project_id: Optional[str] = None,
        max_retries: int = 3,
        **kwargs: Any
    ) -> str:
        """
        Complete a chat message with the LLM.

        Args:
            messages: List of message dicts with role and content
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            operation_type: Optional label for cost tracking (e.g., "analysis", "generation")
            project_id: Optional project UUID for cost tracking
            max_retries: Maximum number of retry attempts on failure (default: 3)
            **kwargs: Additional LiteLLM parameters

        Returns:
            The completion text
        """
        import asyncio
        self._validate_messages(messages)

        # Generate unique call ID for tracking
        api_call_id = str(uuid4())

        # Handle reasoning models (gpt-5, o1, o3, etc.) that don't support custom temperature
        completion_kwargs = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": False,
            **kwargs
        }

        if is_reasoning_model(self.model):
            # Reasoning models only support temperature=1 (or no temperature param)
            # Don't pass temperature at all - let the API use its default
            logger.debug(f"[LLM] Reasoning model detected ({self.model}) - dropping temperature param")
        else:
            completion_kwargs["temperature"] = temperature

        last_exception = None
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    wait_time = min(2 ** attempt, 8)  # Exponential backoff, max 8 seconds
                    logger.info(f"[LLM] Retry attempt {attempt + 1}/{max_retries} after {wait_time}s delay")
                    await asyncio.sleep(wait_time)

                response = await acompletion(**completion_kwargs)

                # Extract the completion text
                content = response.choices[0].message.content

                # Log token usage and cost if available
                if hasattr(response, 'usage') and response.usage:
                    input_tokens = response.usage.prompt_tokens
                    output_tokens = response.usage.completion_tokens
                    cost_usd = self._calculate_cost(input_tokens, output_tokens)

                    logger.info(f"[LLM Usage] {self.model} | {operation_type or 'unknown'} | "
                          f"tokens: {input_tokens}+{output_tokens} | cost: ${cost_usd:.6f}")

                    # Log to database (async, non-blocking)
                    await self._log_cost(
                        api_call_id=api_call_id,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cost_usd=cost_usd,
                        operation_type=operation_type,
                        project_id=project_id
                    )

                # Success!
                if attempt > 0:
                    logger.info(f"[LLM] Completion successful on attempt {attempt + 1}")
                return content

            except Exception as e:
                last_exception = e
                error_msg = str(e)

                # Check if this is a rate limit error
                is_rate_limit = any(keyword in error_msg.lower() for keyword in ['rate limit', 'quota', 'too many requests', '429'])

                if is_rate_limit:
                    logger.warning(f"[LLM] Rate limit detected on attempt {attempt + 1}/{max_retries}: {error_msg}")
                else:
                    logger.warning(f"[LLM] Completion failed on attempt {attempt + 1}/{max_retries}: {error_msg}")

                # If this was the last attempt, raise after the loop
                if attempt == max_retries - 1:
                    break

        # All retries exhausted
        if last_exception:
            error_msg = str(last_exception)
            if any(keyword in error_msg.lower() for keyword in ['rate limit', 'quota', 'too many requests', '429']):
                raise LLMProviderError(
                    f"LLM rate limit exceeded. Please wait a moment and try again. (Attempted {max_retries} times)"
                ) from last_exception
            else:
                raise LLMProviderError(f"LLM completion failed after {max_retries} attempts: {error_msg}") from last_exception
        else:
            raise LLMProviderError("LLM completion failed for unknown reason")
    
    async def complete_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        self._validate_messages(messages)

        # Handle reasoning models
        completion_kwargs = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": True,
            **kwargs
        }

        if is_reasoning_model(self.model):
            logger.debug(f"[LLM Stream] Reasoning model detected ({self.model}) - dropping temperature param")
        else:
            completion_kwargs["temperature"] = temperature

        try:
            response = await acompletion(**completion_kwargs)
            
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
        operation_type: Optional[str] = None,
        project_id: Optional[str] = None,
        **kwargs: Any
    ):
        """Complete with function/tool calling support."""
        self._validate_messages(messages)

        # Generate unique call ID for tracking
        api_call_id = str(uuid4())

        # Handle reasoning models
        completion_kwargs = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "max_tokens": max_tokens,
            "stream": False,
            **kwargs
        }

        if is_reasoning_model(self.model):
            logger.debug(f"[LLM Tools] Reasoning model detected ({self.model}) - dropping temperature param")
        else:
            completion_kwargs["temperature"] = temperature

        try:
            response = await acompletion(**completion_kwargs)

            # Log token usage and cost
            if hasattr(response, 'usage') and response.usage:
                input_tokens = response.usage.prompt_tokens
                output_tokens = response.usage.completion_tokens
                cost_usd = self._calculate_cost(input_tokens, output_tokens)

                logger.info(f"[LLM Usage] {self.model} | {operation_type or 'tools'} | "
                      f"tokens: {input_tokens}+{output_tokens} | cost: ${cost_usd:.6f}")

                await self._log_cost(
                    api_call_id=api_call_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_usd=cost_usd,
                    operation_type=operation_type or "tools",
                    project_id=project_id
                )

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
        operation_type: Optional[str] = None,
        project_id: Optional[str] = None,
        max_retries: int = 3,
        **kwargs: Any
    ) -> dict:
        """
        Generate an image using a vision generation model (e.g., Gemini 2.5 Flash Image).

        The model returns BOTH text description and image.

        Args:
            messages: List of message dicts with role and content
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            operation_type: Optional label for cost tracking
            project_id: Optional project UUID for cost tracking
            max_retries: Maximum number of retry attempts on failure (default: 3)
            **kwargs: Additional parameters

        Returns:
            dict with keys:
                - image_data: base64 decoded bytes
                - mime_type: str (e.g., 'image/png')
                - data_url: str (full data URL with base64 encoding)
                - description: str (text description of changes made)
        """
        import asyncio
        self._validate_messages(messages)

        # Generate unique call ID for tracking
        api_call_id = str(uuid4())

        last_exception = None
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    wait_time = min(2 ** attempt, 10)  # Exponential backoff, max 10 seconds
                    logger.info(f"[VGM] Retry attempt {attempt + 1}/{max_retries} after {wait_time}s delay")
                    await asyncio.sleep(wait_time)

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

                logger.debug(f"[VGM] Extracted description: {description[:100]}..." if len(description) > 100 else f"[VGM] Extracted description: {description}")

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
                                    logger.debug(f"[VGM] Found image in native Gemini structure (inline_data)")
                                    break
                                # Check for object with inline_data attribute
                                elif hasattr(part, 'inline_data') and part.inline_data:
                                    import base64
                                    image_data = base64.b64decode(part.inline_data.data)
                                    mime_type = getattr(part.inline_data, 'mime_type', 'image/png')
                                    logger.debug(f"[VGM] Found image in native Gemini structure (inline_data attr)")
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
                        logger.debug(f"[VGM] Found image in LiteLLM structure")
                    else:
                        raise LLMProviderError(f"Unexpected image URL format: {image_data_url[:50]}")

                if not image_data:
                    # Log response structure for debugging on first failure
                    if attempt == 0:
                        logger.warning(f"[VGM] No image found. Response structure: hasattr(_hidden_params)={hasattr(response, '_hidden_params')}, "
                                     f"hasattr(choice.message.images)={hasattr(choice.message, 'images')}")
                    raise LLMProviderError("No image found in response. Checked both native Gemini and LiteLLM structures.")

                # Create data URL if not already present
                if not image_data_url:
                    import base64
                    base64_string = base64.b64encode(image_data).decode('utf-8')
                    image_data_url = f"data:{mime_type};base64,{base64_string}"

                # Log token usage and cost
                if hasattr(response, 'usage') and response.usage:
                    input_tokens = response.usage.prompt_tokens
                    output_tokens = response.usage.completion_tokens
                    cost_usd = self._calculate_cost(input_tokens, output_tokens)

                    logger.info(f"[VGM Usage] {self.model} | {operation_type or 'image_generation'} | "
                          f"tokens: {input_tokens}+{output_tokens} | cost: ${cost_usd:.6f}")

                    await self._log_cost(
                        api_call_id=api_call_id,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cost_usd=cost_usd,
                        operation_type=operation_type or "image_generation",
                        project_id=project_id
                    )

                # Success! Return the result
                logger.info(f"[VGM] Image generation successful on attempt {attempt + 1}")
                return {
                    "image_data": image_data,
                    "mime_type": mime_type,
                    "data_url": image_data_url,
                    "description": description
                }

            except Exception as e:
                last_exception = e
                error_msg = str(e)

                # Check if this is a rate limit error
                is_rate_limit = any(keyword in error_msg.lower() for keyword in ['rate limit', 'quota', 'too many requests', '429'])

                if is_rate_limit:
                    logger.warning(f"[VGM] Rate limit detected on attempt {attempt + 1}/{max_retries}: {error_msg}")
                else:
                    logger.warning(f"[VGM] Image generation failed on attempt {attempt + 1}/{max_retries}: {error_msg}")

                # If this was the last attempt, we'll raise the exception after the loop
                if attempt == max_retries - 1:
                    break

        # All retries exhausted
        if last_exception:
            error_msg = str(last_exception)
            if any(keyword in error_msg.lower() for keyword in ['rate limit', 'quota', 'too many requests', '429']):
                raise LLMProviderError(
                    f"Image generation rate limit exceeded. Please wait a few moments and try again. "
                    f"(Attempted {max_retries} times)"
                ) from last_exception
            else:
                raise LLMProviderError(f"Image generation failed after {max_retries} attempts: {error_msg}") from last_exception
        else:
            raise LLMProviderError("Image generation failed for unknown reason")
