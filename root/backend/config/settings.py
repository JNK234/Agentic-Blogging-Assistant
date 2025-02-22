import os
from dotenv import load_dotenv
from dataclasses import dataclass
from typing import Optional

@dataclass
class ModelSettings:
    """Base class for model settings"""
    api_key: str
    
    @classmethod
    def validate_required_vars(cls, **kwargs):
        missing = [k for k, v in kwargs.items() if v is None]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

@dataclass
class OpenAISettings(ModelSettings):
    model_name: str = "gpt-3.5-turbo"
    temperature: float = 0.7
    max_tokens: Optional[int] = 1000

@dataclass
class AzureSettings(ModelSettings):
    api_base: str
    api_version: str
    deployment_name: str

@dataclass
class AnthropicSettings(ModelSettings):
    model_name: str = "claude-2"
    temperature: float = 0.7
    max_tokens: Optional[int] = 1000

@dataclass
class DeepseekSettings(ModelSettings):
    model_name: str = "deepseek-chat"
    temperature: float = 0.7
    max_tokens: Optional[int] = 1000

class Settings:
    """Central settings management"""
    def __init__(self):
        load_dotenv()  # Load environment variables from .env
        self._load_settings()

    def _load_settings(self):
        # OpenAI settings
        self.openai = OpenAISettings(
            api_key=os.getenv('OPENAI_API_KEY'),
            model_name=os.getenv('OPENAI_MODEL_NAME', 'gpt-3.5-turbo'),
        )
        
        # Azure OpenAI settings
        self.azure = AzureSettings(
            api_key=os.getenv('AZURE_OPENAI_API_KEY'),
            api_base=os.getenv('AZURE_OPENAI_API_BASE'),
            api_version=os.getenv('AZURE_OPENAI_API_VERSION'),
            deployment_name=os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')
        )
        
        # Anthropic settings
        self.anthropic = AnthropicSettings(
            api_key=os.getenv('ANTHROPIC_API_KEY'),
            model_name=os.getenv('ANTHROPIC_MODEL_NAME', 'claude-2'),
        )
        
        # Deepseek settings
        self.deepseek = DeepseekSettings(
            api_key=os.getenv('DEEPSEEK_API_KEY'),
            model_name=os.getenv('DEEPSEEK_MODEL_NAME', 'deepseek-chat'),
        )

    def get_model_settings(self, provider: str):
        """Get settings for specific model provider"""
        provider = provider.lower()
        settings_map = {
            'openai': self.openai,
            'azure': self.azure,
            'anthropic': self.anthropic,
            'deepseek': self.deepseek
        }
        if provider not in settings_map:
            raise ValueError(f"Unknown provider: {provider}")
        return settings_map[provider]
