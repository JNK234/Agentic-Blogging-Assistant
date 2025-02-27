import logging
from typing import Optional
from .claude_model import ClaudeModel
from .deepseek_model import DeepseekModel
from .openai_model import OpenAIModel
from .azure_model import AzureModel
from ..config.settings import Settings
from root.backend.agents.outline_generator_agent import OutlineGeneratorAgent
from root.backend.agents.blog_draft_generator_agent import BlogDraftGeneratorAgent

class ModelFactory:
    def __init__(self):
        self.settings = Settings()
        
    def create_model(self, provider: str) -> Optional[ClaudeModel | DeepseekModel | OpenAIModel | AzureModel | OutlineGeneratorAgent | BlogDraftGeneratorAgent]:
        """
        Create and return an instance of the specified LLM model.
        
        Args:
            provider: The name of the LLM provider ('claude', or 'openai')
        
        Args:
            provider: The name of the LLM provider ('deepseek', 'claude', or 'openai')
            
        Returns:
            An instance of the specified model class, or None if provider is invalid
            
        Raises:
            ValueError: If the required API key is not found in environment variables
        """
        try:
            provider = provider.lower()
                        
            if provider in ['deepseek', 'claude', 'openai', 'azure']:
                model_settings = self.settings.get_model_settings(provider)
                
                if provider == 'deepseek':
                    return DeepseekModel(model_settings)
                elif provider == 'claude':
                    return ClaudeModel(model_settings)
                elif provider == 'openai':
                    return OpenAIModel(model_settings)
                elif provider == 'azure':
                    return AzureModel(model_settings)
        
            elif provider == 'outline_generator':
                return OutlineGeneratorAgent()
                
            elif provider == 'blog_draft_generator':
                return BlogDraftGeneratorAgent()
                
            return None
            
        except ValueError as e:
            logging.error(f"Failed to create model for provider {provider}: {str(e)}")
            return None
