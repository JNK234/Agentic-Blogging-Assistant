import os
from typing import Optional
from .deepseek_model import DeepseekModel
from .claude_model import ClaudeModel
from .openai_model import OpenAIModel

class ModelFactory:
    @staticmethod
    def create_model(provider: str) -> Optional[DeepseekModel | ClaudeModel | OpenAIModel]:
        """
        Create and return an instance of the specified LLM model.
        
        Args:
            provider: The name of the LLM provider ('deepseek', 'claude', or 'openai')
            
        Returns:
            An instance of the specified model class, or None if provider is invalid
            
        Raises:
            ValueError: If the required API key is not found in environment variables
        """
        provider = provider.lower()
        
        if provider == 'deepseek':
            api_key = os.getenv('DEEPSEEK_API_KEY')
            if not api_key:
                raise ValueError('DEEPSEEK_API_KEY environment variable not found')
            return DeepseekModel()
            
        elif provider == 'claude':
            api_key = os.getenv('ANTHROPIC_API_KEY')
            if not api_key:
                raise ValueError('ANTHROPIC_API_KEY environment variable not found')
            return ClaudeModel()
            
        elif provider == 'openai':
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                raise ValueError('OPENAI_API_KEY environment variable not found')
            return OpenAIModel()
            
        return None
