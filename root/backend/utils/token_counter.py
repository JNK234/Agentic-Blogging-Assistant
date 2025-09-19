# ABOUTME: Token counting and cost calculation utilities for all LLM providers
# ABOUTME: Provides accurate token counting and real-time cost estimation

import tiktoken
from typing import Dict, Optional, Tuple, List
import logging

logger = logging.getLogger(__name__)

class TokenCounter:
    """Universal token counter for all LLM providers"""

    # Updated pricing per 1M tokens (as of January 2025)

    PRICING = {
        # OpenAI Models (per 1M tokens, Jan 2025 refresh and forward-looking tiers)
        "gpt-5": {"input": 12.00, "output": 36.00},
        "gpt-4.1": {"input": 6.00, "output": 18.00},
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-2024-11-20": {"input": 2.50, "output": 10.00},
        "gpt-4o-2024-08-06": {"input": 2.50, "output": 10.00},
        "gpt-4o-2024-05-13": {"input": 5.00, "output": 15.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o-mini-2024-07-18": {"input": 0.15, "output": 0.60},
        "gpt-4-turbo": {"input": 10.00, "output": 30.00},
        "gpt-4": {"input": 30.00, "output": 60.00},
        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
        "o1": {"input": 15.00, "output": 60.00},
        "o1-mini": {"input": 3.00, "output": 12.00},
        
        # Anthropic Claude Models
        "claude-opus-4.1": {"input": 15.00, "output": 75.00},
        "claude-sonnet-4": {"input": 3.00, "output": 15.00},
        "claude-3.5-sonnet": {"input": 3.00, "output": 15.00},
        "claude-3.5-haiku": {"input": 0.80, "output": 4.00},
        "claude-3-opus": {"input": 15.00, "output": 75.00},
        "claude-3-sonnet": {"input": 3.00, "output": 15.00},
        "claude-3-haiku": {"input": 0.25, "output": 1.25},
        
        # Google Gemini Models
        "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
        "gemini-2.5-pro-002": {"input": 1.25, "output": 10.00},
        "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
        "gemini-2.5-flash-002": {"input": 0.30, "output": 2.50},
        "gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40},
        "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
        "gemini-2.0-flash-lite": {"input": 0.075, "output": 0.30},
        "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
        "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
        "gemini-1.5-flash-8b": {"input": 0.0375, "output": 0.15},
        
        # DeepSeek Models
        "deepseek-reasoner": {"input": 0.56, "output": 1.68},
        "deepseek-chat": {"input": 0.56, "output": 1.68},
        "deepseek-v3": {"input": 0.56, "output": 1.68},
        "deepseek-v3.1": {"input": 0.56, "output": 1.68},
        "deepseek-coder": {"input": 0.56, "output": 1.68},
        
        # OpenRouter / Third-party flagships
        "grok-4": {"input": 5.00, "output": 15.00},
        "x-ai/grok-4": {"input": 5.00, "output": 15.00},
        "openai/gpt-oss-120b": {"input": 3.00, "output": 9.00},
        "qwen/qwen-2.5-72b-instruct": {"input": 0.90, "output": 2.70},
        "qwen/qwen3-next-80b-a3b-thinking": {"input": 3.00, "output": 9.00},
        
        # Default fallback pricing
        "default": {"input": 1.00, "output": 2.00}
    }

    def __init__(self):
        """Initialize token counter with encodings for different models"""
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
        """Get the appropriate encoding for a model"""
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
        """Count tokens in text for a specific model"""
        encoding = self.get_encoding(model_name)
        return len(encoding.encode(text))

    def calculate_cost(self, input_tokens: int, output_tokens: int,
                      model_name: str) -> Tuple[float, Dict[str, any]]:
        """
        Calculate cost for token usage

        Note: All pricing is now in per 1M tokens (not per 1K as before)

        Returns:
            Tuple of (total_cost, breakdown_dict)
        """
        # Normalize model name for pricing lookup
        normalized_name = self._normalize_model_name(model_name)

        # Get pricing for model (use default if not found)
        pricing = self.PRICING.get(normalized_name, self.PRICING["default"])

        # Calculate costs (pricing is per 1M tokens now)
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
            "price_per_1m_input": pricing["input"],  # Changed from 1k to 1m
            "price_per_1m_output": pricing["output"],  # Changed from 1k to 1m
            "model": model_name,
            "normalized_model": normalized_name
        }

        return total_cost, breakdown


    def _normalize_model_name(self, model_name: str) -> str:
        """Normalize model name for pricing lookup"""
        model_lower = model_name.lower().strip()

        alias_map = {
            "gpt-5": ["gpt-5", "gpt5"],
            "gpt-4.1": ["gpt-4.1", "gpt4.1", "gpt-4_1", "gpt4_1"],
            "gpt-4o": ["gpt-4o", "gpt4o"],
            "gpt-4o-mini": ["gpt-4o-mini", "gpt4o-mini", "gpt-4o-mini-2024-07-18"],
            "gpt-4-turbo": ["gpt-4-turbo", "gpt4-turbo"],
            "gpt-4": ["gpt-4", "gpt4"],
            "gpt-3.5-turbo": ["gpt-3.5-turbo", "gpt3.5"],
            "o1-mini": ["o1-mini", "o1mini"],
            "o1": ["o1"],
            "claude-opus-4.1": ["claude-4.1-opus", "claude-opus-4.1", "opus-4.1", "opus4.1"],
            "claude-sonnet-4": ["claude-4-sonnet", "claude-sonnet-4"],
            "claude-3.5-sonnet": ["claude-3.5-sonnet", "claude3.5-sonnet"],
            "claude-3.5-haiku": ["claude-3.5-haiku", "claude3.5-haiku"],
            "claude-3-opus": ["claude-3-opus"],
            "claude-3-sonnet": ["claude-3-sonnet"],
            "claude-3-haiku": ["claude-3-haiku"],
            "gemini-2.5-pro": ["gemini-2.5-pro", "gemini2.5-pro", "gemini-2_5-pro", "gemini-2.5-pro-002"],
            "gemini-2.5-flash": ["gemini-2.5-flash", "gemini2.5-flash", "gemini-2.5-flash-002"],
            "gemini-2.5-flash-lite": ["gemini-2.5-flash-lite"],
            "gemini-2.0-flash": ["gemini-2.0-flash", "gemini2.0-flash", "gemini-2_0-flash"],
            "gemini-2.0-flash-lite": ["gemini-2.0-flash-lite"],
            "gemini-1.5-pro": ["gemini-1.5-pro", "gemini1.5-pro"],
            "gemini-1.5-flash": ["gemini-1.5-flash", "gemini1.5-flash"],
            "gemini-1.5-flash-8b": ["gemini-1.5-flash-8b"],
            "deepseek-reasoner": ["deepseek-reasoner", "deepseek-r1"],
            "deepseek-chat": ["deepseek-chat"],
            "deepseek-v3.1": ["deepseek-v3.1", "deepseek-v3", "deepseek-v3-1"],
            "deepseek-coder": ["deepseek-coder"],
            "grok-4": ["grok-4", "x-ai/grok-4", "xai/grok-4", "grok4"],
            "openai/gpt-oss-120b": ["gpt-oss-120b"],
            "qwen/qwen-2.5-72b-instruct": ["qwen-2.5-72b", "qwen2.5-72b"],
            "qwen/qwen3-next-80b-a3b-thinking": ["qwen3-next-80b", "qwen3 a3b"]
        }

        for canonical, aliases in alias_map.items():
            if any(alias in model_lower for alias in aliases):
                return canonical

        if "claude" in model_lower:
            if "haiku" in model_lower:
                return "claude-3.5-haiku"
            if "sonnet" in model_lower:
                return "claude-3.5-sonnet"
            if "opus" in model_lower:
                return "claude-opus-4.1"

        if "gemini" in model_lower:
            if "flash" in model_lower:
                return "gemini-2.5-flash"
            return "gemini-2.5-pro"

        if "deepseek" in model_lower:
            if "coder" in model_lower:
                return "deepseek-coder"
            if "reasoner" in model_lower or "v3" in model_lower:
                return "deepseek-reasoner"
            return "deepseek-chat"

        if "grok" in model_lower:
            return "grok-4"

        if "gpt" in model_lower and "5" in model_lower:
            return "gpt-5"
        if "gpt" in model_lower and "4.1" in model_lower:
            return "gpt-4.1"

        return model_name

    def estimate_cost(self, prompt: str, expected_output_tokens: int,
                     model_name: str) -> Tuple[float, Dict[str, any]]:
        """Estimate cost before making the actual call"""
        input_tokens = self.count_tokens(prompt, model_name)
        return self.calculate_cost(input_tokens, expected_output_tokens, model_name)

    def get_model_pricing_info(self, model_name: str) -> Dict[str, any]:
        """Get pricing information for a specific model"""
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
        """List all models with pricing information"""
        return list(self.PRICING.keys())
