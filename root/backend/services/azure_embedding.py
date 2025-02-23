"""
Azure OpenAI embedding function for ChromaDB.
"""
from typing import List
import logging
from langchain_openai import AzureOpenAIEmbeddings
from root.backend.config.settings import Settings

class AzureEmbeddingFunction:
    """Custom embedding function using Azure OpenAI for ChromaDB."""
    
    def __init__(self):
        """Initialize Azure OpenAI embeddings."""
        try:
            settings = Settings().azure
            self.embeddings = AzureOpenAIEmbeddings(
                azure_deployment=settings.embeddings_deployment_name,
                azure_endpoint=settings.api_base,
                openai_api_key=settings.api_key,
                openai_api_version=settings.api_version,
                chunk_size=1000  # Process in chunks to handle rate limits
            )
            logging.info("Azure OpenAI embeddings initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize Azure OpenAI embeddings: {str(e)}")
            raise
    
    def __call__(self, input: str) -> List[float]:
        """
        Generate embeddings for a single text input.
        
        Args:
            input: The text to generate embeddings for
            
        Returns:
            Embedding as a list of floats
        """
        try:
            # Generate embeddings
            embeddings = self.embeddings.embed_documents([input])
            return embeddings[0]  # Return single embedding
        except Exception as e:
            logging.error(f"Error generating embeddings: {str(e)}")
            raise
