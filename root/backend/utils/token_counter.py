# ABOUTME: Token counting and cost calculation utilities for all LLM providers
# ABOUTME: Uses models/registry.py as the single source of truth for pricing

import tiktoken
from typing import Dict, Tuple, List
import logging

# Import from the single source of truth
from backend.models.registry import (
    get_pricing_dict,
    normalize_model_name as registry_normalize,
    get_pricing
)

logger = logging.getLogger(__name__)


class TokenCounter:
    """Universal token counter for all LLM providers.

    Pricing data is loaded from models/registry.py - the single source of truth.
    """

    def __init__(self):
        """Initialize token counter with encodings for different models."""
        # Load pricing from registry (single source of truth)
        self.PRICING = get_pricing_dict()

        self.encodings = {}

        # Initialize common encodings
        try:
            self.encodings["gpt-3.5-turbo"] = tiktoken.encoding_for_model("gpt-3.5-turbo")
            self.encodings["gpt-4"] = tiktoken.encoding_for_model("gpt-4")
        except:
            # Fallback to cl100k_base for newer models
            self.encodings["default"] = tiktoken.get_encoding("cl100k_base")

        # Claude uses similar tokenization to GPT
        self.encodings["claude"] = self.encodings.get("gpt-4",
                                                      self.encodings.get("default"))

    def get_encoding(self, model_name: str):
        """Get the appropriate encoding for a model."""
        if "gpt" in model_name.lower():
            try:
                return tiktoken.encoding_for_model(model_name)
            except:
                return self.encodings.get("default", tiktoken.get_encoding("cl100k_base"))
        elif "claude" in model_name.lower():
            return self.encodings.get("claude", tiktoken.get_encoding("cl100k_base"))
        else:
            # For Gemini, Deepseek, etc., use cl100k_base
            return self.encodings.get("default", tiktoken.get_encoding("cl100k_base"))

    def count_tokens(self, text: str, model_name: str) -> int:
        """Count tokens in text for a specific model."""
        encoding = self.get_encoding(model_name)
        return len(encoding.encode(text))

    def calculate_cost(self, input_tokens: int, output_tokens: int,
                      model_name: str) -> Tuple[float, Dict[str, any]]:
        """
        Calculate cost for token usage.

        Note: All pricing is in per 1M tokens.

        Returns:
            Tuple of (total_cost, breakdown_dict)
        """
        # Normalize model name using registry function
        normalized_name = self._normalize_model_name(model_name)

        # Get pricing for model (use default if not found)
        pricing = self.PRICING.get(normalized_name, self.PRICING["default"])

        # Calculate costs (pricing is per 1M tokens)
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        total_cost = input_cost + output_cost

        breakdown = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "input_cost": input_cost,
            "output_cost": output_cost,
            "total_cost": total_cost,
            "price_per_1m_input": pricing["input"],
            "price_per_1m_output": pricing["output"],
            "model": model_name,
            "normalized_model": normalized_name
        }

        return total_cost, breakdown

    def _normalize_model_name(self, model_name: str) -> str:
        """Normalize model name for pricing lookup using registry."""
        return registry_normalize(model_name)

    def estimate_cost(self, prompt: str, expected_output_tokens: int,
                     model_name: str) -> Tuple[float, Dict[str, any]]:
        """Estimate cost before making the actual call."""
        input_tokens = self.count_tokens(prompt, model_name)
        return self.calculate_cost(input_tokens, expected_output_tokens, model_name)

    def get_model_pricing_info(self, model_name: str) -> Dict[str, any]:
        """Get pricing information for a specific model."""
        normalized_name = self._normalize_model_name(model_name)
        pricing = self.PRICING.get(normalized_name, self.PRICING["default"])

        return {
            "model": model_name,
            "normalized_model": normalized_name,
            "input_price_per_1m": pricing["input"],
            "output_price_per_1m": pricing["output"],
            "currency": "USD",
            "found": normalized_name in self.PRICING
        }

    def list_supported_models(self) -> List[str]:
        """List all models with pricing information."""
        return list(self.PRICING.keys())
