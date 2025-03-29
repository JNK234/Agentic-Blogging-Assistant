import logging
from typing import Optional, Union, Any
from .claude_model import ClaudeModel
from .deepseek_model import DeepseekModel
from .openai_model import OpenAIModel
from .azure_model import AzureModel
from .openrouter_model import OpenRouterModel
from .gemini_model import GeminiModel  # Import the new GeminiModel
from ..config.settings import Settings

class ModelFactory:
    def __init__(self):
        self.settings = Settings()
        
    def create_model(self, provider: str) -> Optional[Union[ClaudeModel, DeepseekModel, OpenAIModel, AzureModel, OpenRouterModel, GeminiModel]]: # Add GeminiModel to type hint
        """
        Create and return an instance of the specified LLM model.
        
        Args:
            provider: The name of the LLM provider ('deepseek', 'claude', 'openai', 'azure', 'openrouter', 'gemini') # Add gemini to docstring
            
        Returns:
            An instance of the specified model class, or None if provider is invalid
            
        Raises:
            ValueError: If the required API key is not found in environment variables
        """
        try:
            provider = provider.lower()
                        
            if provider in ['deepseek', 'claude', 'openai', 'azure', 'openrouter', 'gemini']: 
                model_settings = self.settings.get_model_settings(provider)
                
                if provider == 'deepseek':
                    return DeepseekModel(model_settings)
                elif provider == 'claude':
                    return ClaudeModel(model_settings)
                elif provider == 'openai':
                    return OpenAIModel(model_settings)
                elif provider == 'azure':
                    return AzureModel(model_settings)
                elif provider == 'openrouter':
                    return OpenRouterModel(model_settings)
                elif provider == 'gemini': # Add case for Gemini
                    return GeminiModel(model_settings)
                
            return None
            
        except ValueError as e:
            logging.error(f"Failed to create model for provider {provider}: {str(e)}")
            return None
