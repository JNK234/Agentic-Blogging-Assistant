"""
Simplified vector store service using ChromaDB for content storage and retrieval.
"""
from chromadb import Client, Settings
from typing import Dict, List, Optional
from root.backend.services.azure_embedding import AzureEmbeddingFunction
import hashlib
import logging
import os

logging.basicConfig(level=logging.INFO)

class VectorStoreService:
    def __init__(self):
        logging.info("Initializing VectorStoreService...")
        try:
            # Setup storage
            os.makedirs("root/data/vector_store", exist_ok=True)
            
            # Initialize ChromaDB
            self.client = Client(Settings(
                persist_directory="root/data/vector_store",
                anonymized_telemetry=False,
                is_persistent=True
            ))
            self.embedding_fn = AzureEmbeddingFunction()

            # Single collection for all content
            self.collection = self.client.get_or_create_collection(
                name="content",
                embedding_function=self.embedding_fn
            )
            
            logging.info("VectorStoreService initialized successfully")
        except Exception as e:
            logging.error(f"Error initializing VectorStoreService: {e}")
            raise
    
    def compute_content_hash(self, content: str, _: str = "") -> str:
        """Generate a unique hash for content."""
        return hashlib.sha256(content.encode()).hexdigest()
    
    def store_content_chunks(
        self,
        chunks: List[str],
        metadata: List[Dict],
        content_hash: str
    ):
        """Store content chunks with metadata."""
        try:
            if not chunks or not metadata or len(chunks) != len(metadata):
                raise ValueError("Invalid chunks or metadata")
                
            # Add content hash and chunk order to metadata
            for i, meta in enumerate(metadata):
                meta["content_hash"] = content_hash
                meta["chunk_order"] = i  # Add chunk order to metadata
            
            embeddings = [self.embedding_fn(chunk) for chunk in chunks]
            
            # Store chunks with ordered IDs
            self.collection.add(
                documents=chunks,
                embeddings=embeddings,
                metadatas=metadata,
                ids=[f"chunk_{content_hash}_{i:04d}" for i in range(len(chunks))]  # Zero-padded ordering
            )
            logging.info(f"Stored {len(chunks)} ordered chunks for hash {content_hash}")
        except ValueError as e:
            logging.error(f"Validation error: {e}")
            raise
        except Exception as e:
            logging.error(f"Error storing content: {e}")
            raise
    
    def search_content(
        self,
        query: Optional[str] = None,
        metadata_filter: Optional[Dict] = None,
        n_results: int = 10
    ) -> List[Dict]:
        """Search content with optional filtering."""
        try:
            where = {}
            if metadata_filter:
                # Convert multiple conditions to ChromaDB's $and operator format
                if len(metadata_filter) > 1:
                    where = {
                        "$and": [
                            {key: value} for key, value in metadata_filter.items()
                        ]
                    }
                else:
                    where = metadata_filter
                logging.debug(f"Using metadata filter: {where}")

            if query:
                results = self.collection.query(
                    query_texts=[query],
                    where=where,
                    n_results=n_results
                )
                documents = results["documents"][0]
                metadatas = results["metadatas"][0]
                distances = results["distances"][0]
            else:
                results = self.collection.get(
                    where=where if where else None,
                    limit=n_results
                )
                if results and results["documents"]:
                    documents = results["documents"]
                    metadatas = results["metadatas"]
                    distances = [0.0] * len(documents)
                else:
                    documents = []
                    metadatas = []
                    distances = []

            # Create result list with order information
            results_list = [
                {
                    "content": doc,
                    "metadata": meta,
                    "relevance": 1 - (dist / 2),
                    "order": meta.get("chunk_order", 0)  # Get chunk order from metadata
                }
                for doc, meta, dist in zip(documents, metadatas, distances)
            ]

            # Sort results by chunk order if not using query-based search
            if not query:
                results_list.sort(key=lambda x: x["order"])

            return results_list

        except Exception as e:
            logging.error(f"Error searching content: {e}")
            return []
    
    def clear_content(self, content_hash: str):
        """Remove content by hash."""
        try:
            self.collection.delete(
                where={"content_hash": content_hash}
            )
            logging.info(f"Cleared content for hash {content_hash}")
        except Exception as e:
            logging.error(f"Error clearing content: {e}")
