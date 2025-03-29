"""
Sentence Transformer embedding function for ChromaDB using Hugging Face models.
"""
from typing import List
import logging
from chromadb import Documents, EmbeddingFunction, Embeddings
from sentence_transformers import SentenceTransformer
from root.backend.config.settings import Settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SentenceTransformerEmbeddingFunction(EmbeddingFunction):
    """
    Custom embedding function using Sentence Transformers models from Hugging Face
    for ChromaDB.
    """

    def __init__(self, model_name: str = None):
        """
        Initialize the Sentence Transformer model.

        Args:
            model_name (str, optional): The name of the Sentence Transformer model
                                        to use from Hugging Face Hub. If None,
                                        it loads from settings.
                                        Defaults to None.
        """
        try:
            if model_name is None:
                settings = Settings()
                # Ensure sentence_transformer settings are loaded
                if not hasattr(settings, 'sentence_transformer') or not settings.sentence_transformer.model_name:
                    raise ValueError("Sentence Transformer model name not found in settings.")
                self.model_name = settings.sentence_transformer.model_name
            else:
                 self.model_name = model_name

            # Load the Sentence Transformer model
            # You might want to specify device='cuda' if GPU is available and configured
            self.model = SentenceTransformer(self.model_name)
            logger.info(f"Sentence Transformer model '{self.model_name}' initialized successfully.")

        except ImportError:
            logger.error("sentence-transformers library not found. Please install it using 'pip install sentence-transformers'")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Sentence Transformer model '{self.model_name}': {str(e)}")
            raise

    def __call__(self, input: Documents) -> Embeddings:
        """
        Generate embeddings for documents following ChromaDB's EmbeddingFunction protocol.

        Args:
            input: List of text documents to embed.

        Returns:
            List of embeddings, where each embedding is a list of floats.
        """
        try:
            # Check if input is empty
            if not input:
                logger.warning("Received empty input list for embedding.")
                return []

            # Generate embeddings using the loaded Sentence Transformer model
            # The model's encode function returns numpy arrays; convert them to lists
            logger.info(f"Generating embeddings for {len(input)} documents using {self.model_name}...")
            embeddings = self.model.encode(input, convert_to_numpy=True)
            logger.info(f"Successfully generated {len(embeddings)} embeddings.")
            return embeddings

        except Exception as e:
            logger.error(f"Error generating embeddings with {self.model_name}: {str(e)}")
            # Depending on the desired behavior, you might want to return empty list
            # or partial results if applicable, but raising is often safer.
            raise
