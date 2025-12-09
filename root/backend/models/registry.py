# ABOUTME: Single source of truth for all LLM model configurations
# ABOUTME: Provides model metadata, pricing, and aliases used throughout the application

"""
Model Registry - Centralized model configuration for the Agentic Blogging Assistant.

This module is the SINGLE SOURCE OF TRUTH for:
- Available models and their metadata
- Pricing information (per 1M tokens)
- Model aliases for normalization
- Provider groupings for UI display

OPTIMIZED FOR: Creative Writing & Blogging (December 2025 Research)

To add a new model:
1. Add entry to MODELS dict with all required fields
2. Add aliases to ALIASES dict if needed
3. The change will automatically propagate to:
   - /models API endpoint
   - Token cost calculations
   - Frontend model dropdowns

Last Updated: December 2025
Writing Rankings Applied: Based on comprehensive research of model writing capabilities
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class ModelInfo:
    """Model configuration data class."""
    id: str
    name: str
    provider: str
    description: str
    input_price_per_1m: float
    output_price_per_1m: float
    max_tokens: int = 4096
    is_default: bool = False


# ============================================================================
# SINGLE SOURCE OF TRUTH: All available models
# ============================================================================

MODELS: Dict[str, ModelInfo] = {
    # -------------------------------------------------------------------------
    # OpenAI Models (Updated December 2025 - Writing Optimized)
    # -------------------------------------------------------------------------
    # Best for Creative Writing & Blogging
    "gpt-5.1-thinking": ModelInfo(
        id="gpt-5.1-thinking",
        name="GPT-5.1 Thinking",
        provider="openai",
        description="Top-tier creative writing, storytelling, and blogging",
        input_price_per_1m=1.25,
        output_price_per_1m=10.00,
        max_tokens=400000,
        is_default=True
    ),
    "gpt-5-mini": ModelInfo(
        id="gpt-5-mini",
        name="GPT-5 Mini",
        provider="openai",
        description="Balanced writing quality and speed for daily blogging",
        input_price_per_1m=0.25,
        output_price_per_1m=2.00,
        max_tokens=272000
    ),
    "gpt-5-nano": ModelInfo(
        id="gpt-5-nano",
        name="GPT-5 Nano",
        provider="openai",
        description="Affordable writing for high-volume content",
        input_price_per_1m=0.05,
        output_price_per_1m=0.40,
        max_tokens=272000
    ),
    "o4-mini": ModelInfo(
        id="o4-mini",
        name="O4 Mini",
        provider="openai",
        description="Fast reasoning for structured content and articles",
        input_price_per_1m=1.10,
        output_price_per_1m=4.40,
        max_tokens=200000
    ),
    "o1": ModelInfo(
        id="o1",
        name="O1",
        provider="openai",
        description="Advanced reasoning for complex technical blogs",
        input_price_per_1m=15.00,
        output_price_per_1m=60.00,
        max_tokens=128000
    ),

    # -------------------------------------------------------------------------
    # Anthropic Claude Models (Updated December 2025 - Writing Optimized)
    # -------------------------------------------------------------------------
    # Best for Creative Writing & Blogging
    "claude-opus-4.5": ModelInfo(
        id="claude-opus-4.5",
        name="Claude Opus 4.5",
        provider="claude",
        description="Exceptional prose, creative storytelling, and editorial quality",
        input_price_per_1m=5.00,
        output_price_per_1m=25.00,
        max_tokens=200000,
        is_default=True
    ),
    "claude-sonnet-4.5": ModelInfo(
        id="claude-sonnet-4.5",
        name="Claude Sonnet 4.5",
        provider="claude",
        description="Balanced writing quality for articles and blogs",
        input_price_per_1m=3.00,
        output_price_per_1m=15.00,
        max_tokens=200000
    ),
    "claude-haiku-4.5": ModelInfo(
        id="claude-haiku-4.5",
        name="Claude Haiku 4.5",
        provider="claude",
        description="Fast, efficient writing for daily content",
        input_price_per_1m=1.00,
        output_price_per_1m=5.00,
        max_tokens=200000
    ),

    # -------------------------------------------------------------------------
    # Google Gemini Models (Updated December 2025 - Writing Ranked)
    # -------------------------------------------------------------------------
    # Rankings Based on Research: Writing Quality Scores
    "gemini-3-pro-preview": ModelInfo(
        id="gemini-3-pro-preview",
        name="Gemini 3 Pro ⭐",
        provider="gemini",
        description="Top writing score (9.0/10) - Best for creative blogs & long-form",
        input_price_per_1m=2.00,
        output_price_per_1m=12.00,
        max_tokens=1048576,
        is_default=True
    ),
    "gemini-2.5-pro": ModelInfo(
        id="gemini-2.5-pro",
        name="Gemini 2.5 Pro",
        provider="gemini",
        description="High writing score (8.5/10) - Excellent for technical blogs",
        input_price_per_1m=1.25,
        output_price_per_1m=10.00,
        max_tokens=1048576
    ),
    "gemini-2.5-flash": ModelInfo(
        id="gemini-2.5-flash",
        name="Gemini 2.5 Flash",
        provider="gemini",
        description="Good writing score (7.5/10) - Fast daily blog posts",
        input_price_per_1m=0.30,
        output_price_per_1m=2.50,
        max_tokens=1048576
    ),
    "gemini-2.5-flash-lite": ModelInfo(
        id="gemini-2.5-flash-lite",
        name="Gemini 2.5 Flash Lite",
        provider="gemini",
        description="Budget writing (6.5/10) - High-volume content",
        input_price_per_1m=0.10,
        output_price_per_1m=0.40,
        max_tokens=1048576
    ),
    "gemini-2.0-flash-lite": ModelInfo(
        id="gemini-2.0-flash-lite",
        name="Gemini 2.0 Flash Lite",
        provider="gemini",
        description="Basic writing (6.0/10) - Quick drafts",
        input_price_per_1m=0.075,
        output_price_per_1m=0.30,
        max_tokens=1048576
    ),

    # -------------------------------------------------------------------------
    # DeepSeek Models (Updated December 2025 - Note: Coding-focused)
    # -------------------------------------------------------------------------
    # Note: Research shows DeepSeek models excel at coding, limited for creative writing
    "deepseek-reasoner": ModelInfo(
        id="deepseek-reasoner",
        name="DeepSeek-R1",
        provider="deepseek",
        description="Coding-focused with reasoning - for technical blogs",
        input_price_per_1m=0.28,
        output_price_per_1m=0.42,
        max_tokens=128000,
        is_default=True
    ),
    "deepseek-chat": ModelInfo(
        id="deepseek-chat",
        name="DeepSeek Chat V3.2",
        provider="deepseek",
        description="Technical writing specialist - great for dev blogs",
        input_price_per_1m=0.28,
        output_price_per_1m=0.42,
        max_tokens=128000
    ),
    "deepseek-coder": ModelInfo(
        id="deepseek-coder",
        name="DeepSeek Coder V2",
        provider="deepseek",
        description="Code generation expert - for programming tutorials",
        input_price_per_1m=0.14,
        output_price_per_1m=0.28,
        max_tokens=128000
    ),

    # -------------------------------------------------------------------------
    # OpenRouter Models (Updated December 2025 - Writing Optimized)
    # -------------------------------------------------------------------------
    # Top Writers Based on Research: Writing Quality Rankings
    "mistral-large-2-2407": ModelInfo(
        id="mistral-large-2-2407",
        name="Mistral Large 2 ⭐⭐⭐",
        provider="openrouter",
        description="TOP WRITER (9.5/10) - Exceptional prose, storytelling, blogs",
        input_price_per_1m=0.50,
        output_price_per_1m=1.50,
        max_tokens=256000,
        is_default=True
    ),
    "qwen-3-72b-instruct": ModelInfo(
        id="qwen-3-72b-instruct",
        name="Qwen 3 72B Instruct ⭐⭐",
        provider="openrouter",
        description="EXCELLENT WRITER (9.0/10) - Versatile, multilingual blogs",
        input_price_per_1m=0.90,
        output_price_per_1m=2.70,
        max_tokens=131072
    ),
    "deepseek-v3-chat": ModelInfo(
        id="deepseek-v3-chat",
        name="DeepSeek V3 Chat ⭐",
        provider="openrouter",
        description="GOOD WRITER (8.5/10) - Technical blogs & developer content",
        input_price_per_1m=0.28,
        output_price_per_1m=0.42,
        max_tokens=163840
    ),
    "mistral-medium-3": ModelInfo(
        id="mistral-medium-3",
        name="Mistral Medium 3",
        provider="openrouter",
        description="Balanced writing - fast daily content",
        input_price_per_1m=0.20,
        output_price_per_1m=0.60,
        max_tokens=128000
    ),
    "qwen-2.5-72b-instruct": ModelInfo(
        id="qwen-2.5-72b-instruct",
        name="Qwen 2.5 72B Instruct",
        provider="openrouter",
        description="Solid writing quality for general blogs",
        input_price_per_1m=0.90,
        output_price_per_1m=2.70,
        max_tokens=131072
    ),
}


# ============================================================================
# Model Aliases for normalization (maps variations to canonical IDs)
# ============================================================================

ALIASES: Dict[str, str] = {
    # OpenAI aliases
    "gpt5": "gpt-5.1-thinking",
    "gpt5.1": "gpt-5.1-thinking",
    "gpt-5": "gpt-5-mini",
    "o4": "o4-mini",
    "o3": "o3-mini",
    "o1": "o1",
    "o1-mini": "o1-mini",
    "gpt-5-nano": "gpt-5-nano",
    "gpt5nano": "gpt-5-nano",
    "gpt-4.1-nano": "gpt-4.1-nano",
    "gpt4.1nano": "gpt-4.1-nano",
    "gpt-4o": "gpt-4o-mini",
    "gpt4o": "gpt-4o-mini",

    # Claude aliases
    "claude-opus-4.5": "claude-opus-4.5",
    "opus-4.5": "claude-opus-4.5",
    "claude-sonnet-4.5": "claude-sonnet-4.5",
    "sonnet-4.5": "claude-sonnet-4.5",
    "claude-haiku-4.5": "claude-haiku-4.5",
    "haiku-4.5": "claude-haiku-4.5",
    "claude-opus-4.1": "claude-opus-4.5",
    "claude-sonnet-4": "claude-sonnet-4.5",

    # Gemini 3 aliases
    "gemini-3-pro-preview": "gemini-3-pro-preview",
    "gemini3-pro-preview": "gemini-3-pro-preview",
    "gemini-3.0-pro": "gemini-3-pro-preview",
    "gemini-3-pro": "gemini-3-pro-preview",
    "gemini-3-flash": "gemini-2.5-flash",
    "gemini3-flash": "gemini-2.5-flash",

    # Gemini 2.5 aliases
    "gemini2.5-pro": "gemini-2.5-pro",
    "gemini-2_5-pro": "gemini-2.5-pro",
    "gemini-2.5-pro-002": "gemini-2.5-pro",
    "gemini2.5-flash": "gemini-2.5-flash",
    "gemini-2.5-flash-002": "gemini-2.5-flash",
    "gemini2.5-flash-lite": "gemini-2.5-flash-lite",
    "gemini-2.5-flash-lite": "gemini-2.5-flash-lite",
    "gemini2.0-flash": "gemini-2.0-flash-lite",
    "gemini-2_0-flash": "gemini-2.0-flash-lite",
    "gemini2.0-flash-lite": "gemini-2.0-flash-lite",

    # DeepSeek aliases
    "deepseek-r1": "deepseek-reasoner",
    "deepseek-v3.2": "deepseek-chat",
    "deepseek-v3.2-exp": "deepseek/deepseek-v3.2-exp",
    "deepseek-reasoner": "deepseek-reasoner",
    "deepseek-chat": "deepseek-chat",
    "deepseek-coder": "deepseek-coder",

    # OpenRouter aliases (Writing-Optimized Models)
    "mistral-large-2": "mistral-large-2-2407",
    "mistral-large": "mistral-large-2-2407",
    "qwen3": "qwen-3-72b-instruct",
    "qwen-3": "qwen-3-72b-instruct",
    "qwen-3-72b": "qwen-3-72b-instruct",
    "qwen3-72b": "qwen-3-72b-instruct",
    "deepseek-v3-chat": "deepseek-v3-chat",
    "deepseekv3chat": "deepseek-v3-chat",
    "mistral-medium": "mistral-medium-3",
    "mistral-medium-3": "mistral-medium-3",
    "qwen-2.5-72b": "qwen-2.5-72b-instruct",
    "qwen2.5-72b": "qwen-2.5-72b-instruct",
    # Legacy aliases (map to new models)
    "grok-4": "mistral-large-2-2407",
    "x-ai/grok-4": "mistral-large-2-2407",
    "qwen/qwen-2.5-coder-32b-instruct": "qwen-3-72b-instruct",
    "mistralai/mistral-large-3-2512": "mistral-large-2-2407",
}


# ============================================================================
# Provider metadata
# ============================================================================

PROVIDERS: Dict[str, Dict[str, str]] = {
    "openai": {
        "name": "OpenAI",
        "description": "GPT models for versatile AI tasks"
    },
    "claude": {
        "name": "Anthropic Claude",
        "description": "Advanced conversational AI with safety focus"
    },
    "gemini": {
        "name": "Google Gemini",
        "description": "Google's multimodal AI models with strong reasoning"
    },
    "deepseek": {
        "name": "DeepSeek",
        "description": "Efficient models optimized for coding and reasoning"
    },
    "openrouter": {
        "name": "OpenRouter",
        "description": "Access to multiple models through one API"
    }
}


# ============================================================================
# Helper functions
# ============================================================================

def get_model(model_id: str) -> Optional[ModelInfo]:
    """Get model info by ID or alias."""
    # Check direct ID first
    if model_id in MODELS:
        return MODELS[model_id]

    # Check aliases
    normalized = model_id.lower().strip()
    if normalized in ALIASES:
        canonical_id = ALIASES[normalized]
        return MODELS.get(canonical_id)

    # Try case-insensitive lookup
    for key, model in MODELS.items():
        if key.lower() == normalized:
            return model

    return None


def normalize_model_name(model_name: str) -> str:
    """Normalize model name to canonical ID."""
    model_lower = model_name.lower().strip()

    # Direct match
    if model_lower in MODELS:
        return model_lower

    # Alias match
    if model_lower in ALIASES:
        return ALIASES[model_lower]

    # Partial match in aliases
    for alias, canonical in ALIASES.items():
        if alias in model_lower:
            return canonical

    # Fallback heuristics by provider keywords
    if "claude" in model_lower:
        if "haiku" in model_lower:
            return "claude-haiku-4.5"
        if "sonnet" in model_lower:
            return "claude-sonnet-4.5"
        if "opus" in model_lower:
            return "claude-opus-4.5"

    if "gemini" in model_lower:
        if "3" in model_lower:
            return "gemini-3-pro-preview"
        if "flash" in model_lower:
            return "gemini-2.5-flash"
        return "gemini-2.5-pro"

    if "deepseek" in model_lower:
        if "coder" in model_lower:
            return "deepseek-coder"
        if "reasoner" in model_lower or "r1" in model_lower:
            return "deepseek-reasoner"
        return "deepseek-chat"

    if "grok" in model_lower:
        return "x-ai/grok-4"

    if "gpt" in model_lower:
        if "nano" in model_lower:
            return "gpt-5-nano"
        if "o4" in model_lower or "o3" in model_lower:
            return "o4-mini"
        if "o1" in model_lower:
            return "o1"
        return "gpt-5.1-thinking"

    # Return original if no match
    return model_name


def get_pricing(model_id: str) -> Dict[str, float]:
    """Get pricing for a model (per 1M tokens)."""
    model = get_model(model_id)
    if model:
        return {
            "input": model.input_price_per_1m,
            "output": model.output_price_per_1m
        }
    # Default fallback pricing
    return {"input": 1.00, "output": 2.00}


def get_models_by_provider(provider: str) -> List[ModelInfo]:
    """Get all models for a specific provider."""
    return [m for m in MODELS.values() if m.provider == provider]


def get_default_model(provider: str) -> Optional[ModelInfo]:
    """Get the default model for a provider."""
    provider_models = get_models_by_provider(provider)
    for model in provider_models:
        if model.is_default:
            return model
    return provider_models[0] if provider_models else None


def get_all_providers() -> List[str]:
    """Get list of all available providers."""
    return list(PROVIDERS.keys())


def get_provider_info(provider: str) -> Dict[str, str]:
    """Get provider metadata."""
    return PROVIDERS.get(provider, {"name": provider.title(), "description": ""})


def get_pricing_dict() -> Dict[str, Dict[str, float]]:
    """
    Get pricing dictionary in the format expected by TokenCounter.
    Returns: {model_id: {"input": price, "output": price}}
    """
    pricing = {}
    for model_id, model in MODELS.items():
        pricing[model_id] = {
            "input": model.input_price_per_1m,
            "output": model.output_price_per_1m
        }
    # Add default fallback
    pricing["default"] = {"input": 1.00, "output": 2.00}
    return pricing


def get_api_models_response() -> Dict[str, Any]:
    """
    Get models formatted for the /models API endpoint.
    Returns: {"providers": {provider_id: {"name": str, "models": [...]}}}
    """
    providers_response = {}

    for provider_id, provider_info in PROVIDERS.items():
        provider_models = get_models_by_provider(provider_id)

        # Sort models: default first, then alphabetically
        sorted_models = sorted(
            provider_models,
            key=lambda m: (not m.is_default, m.name)
        )

        providers_response[provider_id] = {
            "name": provider_info["name"],
            "models": [
                {
                    "id": m.id,
                    "name": m.name,
                    "description": m.description
                }
                for m in sorted_models
            ]
        }

    return {"providers": providers_response}
