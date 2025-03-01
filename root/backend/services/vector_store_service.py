"""
Simplified vector store service using ChromaDB for content storage and retrieval.
Supports caching of generated outlines for efficient retrieval.
"""
from chromadb import Client, Settings
from typing import Dict, List, Optional
from root.backend.services.azure_embedding import AzureEmbeddingFunction
import hashlib
import logging
import os
from datetime import datetime

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
            
    def store_outline_cache(self, outline_json: str, cache_key: str, project_name: str, source_hashes: List[str]):
        """Store a generated outline with metadata for caching.
        
        Args:
            outline_json: The JSON string representation of the outline
            cache_key: A deterministic key generated from input parameters
            project_name: The project name for organization
            source_hashes: List of content hashes used to generate the outline
        """
        try:
            # Create metadata for the outline cache
            metadata = {
                "content_type": "outline_cache",
                "project_name": project_name,
                "cache_key": cache_key,
                "source_hashes": ",".join(filter(None, source_hashes)),  # Join non-None hashes
                "timestamp": datetime.now().isoformat()
            }
            
            embeddings = [self.embedding_fn(chunk) for chunk in [outline_json]]
            
            # Store the outline as a single document - ChromaDB expects a list of documents
            # but the embedding function expects a single string
            self.collection.add(
                documents=[outline_json],  # Keep as a list with a single string
                metadatas=[metadata],
                ids=[f"outline_{cache_key}"],
                embeddings=embeddings  # Skip embedding generation, let ChromaDB handle it
            )
            
            logging.info(f"Cached outline with key {cache_key} for project {project_name}")
            return True
        except Exception as e:
            logging.error(f"Error caching outline: {e}")
            return False
    
    def retrieve_outline_cache(self, cache_key: str, project_name: Optional[str] = None) -> Optional[str]:
        """Retrieve a cached outline based on cache key and optional project name.
        
        Args:
            cache_key: The cache key to look up
            project_name: Optional project name for additional filtering
            
        Returns:
            The cached outline JSON string or None if not found
        """
        try:
            # Build the query filter
            if project_name:
                # Use $and operator for multiple conditions
                where = {
                    "$and": [
                        {"content_type": "outline_cache"},
                        {"cache_key": cache_key},
                        {"project_name": project_name}
                    ]
                }
            else:
                # Use $and operator for multiple conditions
                where = {
                    "$and": [
                        {"content_type": "outline_cache"},
                        {"cache_key": cache_key}
                    ]
                }
                
            # Query for the cached outline
            results = self.collection.get(
                where=where,
                limit=1
            )
            
            if results and results["documents"] and len(results["documents"]) > 0:
                logging.info(f"Found cached outline with key {cache_key}")
                return results["documents"][0]
            else:
                logging.info(f"No cached outline found with key {cache_key}")
                return None
        except Exception as e:
            logging.error(f"Error retrieving cached outline: {e}")
            return None
            
    def clear_outline_cache(self, project_name: Optional[str] = None):
        """Clear cached outlines, optionally filtered by project name.
        
        Args:
            project_name: Optional project name to clear caches for
        """
        try:
            if project_name:
                # Use $and operator for multiple conditions
                where = {
                    "$and": [
                        {"content_type": "outline_cache"},
                        {"project_name": project_name}
                    ]
                }
            else:
                where = {"content_type": "outline_cache"}
                
            self.collection.delete(where=where)
            
            if project_name:
                logging.info(f"Cleared outline cache for project {project_name}")
            else:
                logging.info("Cleared all outline caches")
        except Exception as e:
            logging.error(f"Error clearing outline cache: {e}")
