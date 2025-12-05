import os
from dotenv import load_dotenv
from dataclasses import dataclass, field
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
    model_name: str = "gpt-5"
    temperature: float = 0.7
    max_tokens: Optional[int] = 1000

@dataclass
class SentenceTransformerSettings:
    """Settings specific to Sentence Transformer models."""
    model_name: str = "all-MiniLM-L6-v2" # Default to a popular lightweight model

@dataclass
class AzureSettings(ModelSettings):
    api_base: str
    api_version: str
    deployment_name: str
    embeddings_deployment_name: str
    # model_name: str = "gpt-4o"
    max_tokens: Optional[int] = 1000
    
@dataclass
class AnthropicSettings(ModelSettings):
    model_name: str = "claude-opus-4.1"
    temperature: float = 0.7
    max_tokens: Optional[int] = 1000

@dataclass
class DeepseekSettings(ModelSettings):
    model_name: str = "deepseek-chat"
    temperature: float = 0.7
    max_tokens: Optional[int] = 1000

@dataclass
class GeminiSettings(ModelSettings):
    """Settings specific to Google Gemini models."""
    model_name: Optional[str] = "gemini-3-pro-preview" # Default model (Gemini 3.0 Pro)
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 8192 # Gemini 3.0 supports up to 64K output tokens

@dataclass
class OpenRouterSettings(ModelSettings):
    base_url: str = " https://openrouter.ai/api/v1/chat/completions"
    model_name: str = "x-ai/grok-4"
    headers: dict = field(default_factory=lambda: {
        "HTTP-Referer": os.getenv('OPENROUTER_REFERER_URL'),
        "X-Title": os.getenv('OPENROUTER_APP_NAME')
    })
    max_tokens: Optional[int] = 1000

class Settings:
    """Central settings management"""
    def __init__(self):
        load_dotenv()  # Load environment variables from .env
        self._load_settings()

    def _load_settings(self):
        # --- Embedding Provider Selection ---
        self.embedding_provider = os.getenv('EMBEDDING_PROVIDER', 'sentence_transformer').lower() # Default to sentence_transformer

        # --- LLM Provider Settings ---
        # OpenAI settings
        self.openai = OpenAISettings(
            api_key=os.getenv('OPENAI_API_KEY'),
            model_name=os.getenv('OPENAI_MODEL_NAME', 'gpt-5'),
            max_tokens=os.getenv('OPENAI_MAX_TOKENS', 4096)
        )
        
        # Azure OpenAI settings
        self.azure = AzureSettings(
            api_key=os.getenv('AZURE_OPENAI_API_KEY'),
            api_base=os.getenv('AZURE_OPENAI_API_BASE'),
            api_version=os.getenv('AZURE_OPENAI_API_VERSION'),
            deployment_name=os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME'),
            embeddings_deployment_name=os.getenv('AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT_NAME'),
            # model_name=os.getenv('AZURE_OPENAI_MODEL_NAME', 'gpt-4o')
            max_tokens=os.getenv('AZURE_MAX_TOKENS', 4096)
        )
        
        # Anthropic settings
        self.anthropic = AnthropicSettings(
            api_key=os.getenv('ANTHROPIC_API_KEY'),
            model_name=os.getenv('ANTHROPIC_MODEL_NAME', 'claude-opus-4.1'),
            max_tokens=os.getenv('ANTHROPIC_MAX_TOKENS', 4096)
        )
        
        # Deepseek settings
        self.deepseek = DeepseekSettings(
            api_key=os.getenv('DEEPSEEK_API_KEY'),
            model_name=os.getenv('DEEPSEEK_MODEL_NAME', 'deepseek-reasoner'),
            max_tokens=os.getenv('DEEPSEEK_MAX_TOKENS', 4096)
        )

        # OpenRouter settings
        self.openrouter = OpenRouterSettings(
            api_key=os.getenv('OPENROUTER_API_KEY'),
            model_name=os.getenv('OPENROUTER_MODEL_NAME', 'x-ai/grok-4'),
            max_tokens=os.getenv('OPENROUTER_MAX_TOKENS', 4096)
        )

        # Gemini settings
        self.gemini = GeminiSettings(
            api_key=os.getenv('GEMINI_API_KEY'),
            model_name=os.getenv('GEMINI_MODEL_NAME', 'gemini-3-pro-preview'),
            max_tokens=os.getenv('GEMINI_MAX_TOKENS', 8192)
        )

        # --- Embedding Provider Settings ---
        # Sentence Transformer settings (only model name needed for now)
        self.sentence_transformer = SentenceTransformerSettings(
            model_name=os.getenv('SENTENCE_TRANSFORMER_MODEL_NAME', 'all-MiniLM-L6-v2')
        )
        # Note: Azure embedding settings are already loaded under self.azure

        # --- Supabase Settings ---
        self.supabase_url = os.getenv('SUPABASE_URL', '')
        self.supabase_key = os.getenv('SUPABASE_KEY', '')

    def get_model_settings(self, provider: str):
        """Get settings for specific LLM provider"""
        provider = provider.lower()
        settings_map = {
            'openai': self.openai,
            'azure': self.azure,
            'claude': self.anthropic, # Note: Claude uses AnthropicSettings
            'deepseek': self.deepseek,
            'openrouter': self.openrouter,
            'gemini': self.gemini, # Add gemini mapping
        }
        if provider not in settings_map:
            raise ValueError(f"Unknown provider: {provider}")
        return settings_map[provider]
