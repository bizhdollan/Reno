import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv(override=True)


@dataclass
class LLMConfig:
    provider: str
    model: str
    api_key: str
    
    @classmethod
    def from_env(cls) -> "LLMConfig":
        provider = os.getenv("LLM_PROVIDER")
        model = os.getenv("LLM_MODEL")
        api_key = os.getenv("LLM_API_KEY")
        
        if not provider:
            raise ValueError("LLM_PROVIDER environment variable is required")
        if not model:
            raise ValueError("LLM_MODEL environment variable is required")
        if not api_key:
            raise ValueError("LLM_API_KEY environment variable is required")
        
        return cls(provider=provider, model=model, api_key=api_key)


def get_llm_config() -> LLMConfig:
    return LLMConfig.from_env()


@dataclass
class VLMConfig:
    provider: str
    model: str
    api_key: str
    
    @classmethod
    def from_env(cls) -> "VLMConfig":
        provider = os.getenv("VLM_PROVIDER")
        model = os.getenv("VLM_MODEL")
        api_key = os.getenv("VLM_API_KEY")
        
        # Fallback to LLM config if VLM not set
        if not provider or not model or not api_key:
            llm_config = LLMConfig.from_env()
            return cls(
                provider=llm_config.provider,
                model=llm_config.model,
                api_key=llm_config.api_key
            )
        
        return cls(provider=provider, model=model, api_key=api_key)


def get_vlm_config() -> VLMConfig:
    return VLMConfig.from_env()


@dataclass
class VGMConfig:
    """Vision Generation Model config - for image generation (e.g., Gemini 2.5 Flash Image)"""
    provider: str
    model: str
    api_key: str

    @classmethod
    def from_env(cls) -> "VGMConfig":
        # VGM is specifically for Gemini image generation
        provider = os.getenv("GEMINI_IGM_PROVIDER", "gemini")
        model = os.getenv("GEMINI_IGM_MODEL", "gemini/gemini-2.5-flash-image")
        api_key = os.getenv("GEMINI_IGM_API_KEY")

        if not api_key:
            raise ValueError("GEMINI_IGM_API_KEY environment variable is required for image generation")

        return cls(provider=provider, model=model, api_key=api_key)


def get_vgm_config() -> VGMConfig:
    return VGMConfig.from_env()
