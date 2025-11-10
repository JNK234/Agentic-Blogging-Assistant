"""
Factory for creating embedding function instances based on configuration.
"""
import logging
from chromadb import EmbeddingFunction
from backend.config.settings import Settings
from backend.models.embeddings.azure_embedding import AzureEmbeddingFunction
from backend.models.embeddings.sentence_transformer_embedding import SentenceTransformerEmbeddingFunction

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmbeddingFactory:
    """
    Factory class to create and return the configured embedding function.
    """

    @staticmethod
    def get_embedding_function() -> EmbeddingFunction:
        """
        Reads the configuration and returns an instance of the
        selected embedding function (Azure or Sentence Transformer).

        Returns:
            EmbeddingFunction: An instance of the configured embedding function.

        Raises:
            ValueError: If the configured embedding provider is unknown.
        """
        settings = Settings()
        provider = settings.embedding_provider

        logger.info(f"Selected embedding provider: {provider}")

        if provider == 'azure':
            logger.info("Initializing Azure OpenAI Embedding Function...")
            # AzureEmbeddingFunction reads its own settings internally
            return AzureEmbeddingFunction()
        elif provider == 'sentence_transformer':
            logger.info("Initializing Sentence Transformer Embedding Function...")
            # Pass the model name from settings
            model_name = settings.sentence_transformer.model_name
            logger.info(f"Using Sentence Transformer model: {model_name}")
            return SentenceTransformerEmbeddingFunction(model_name=model_name)
        else:
            logger.error(f"Unknown embedding provider configured: {provider}")
            raise ValueError(f"Unknown embedding provider: {provider}. Please choose 'azure' or 'sentence_transformer'.")

# Example usage (optional, for testing)
if __name__ == '__main__':
    try:
        # This assumes you have a .env file configured correctly in the root
        embedding_func = EmbeddingFactory.get_embedding_function()
        logger.info(f"Successfully created embedding function: {type(embedding_func).__name__}")

        # Example: Test embedding a simple document list
        if embedding_func:
             docs_to_embed = ["This is a test document.", "Another test document."]
             embeddings = embedding_func(docs_to_embed)
             logger.info(f"Generated {len(embeddings)} embeddings.")
             if embeddings:
                 logger.info(f"Dimension of the first embedding: {len(embeddings[0])}")

    except Exception as e:
        logger.error(f"Error during embedding factory test: {e}")
