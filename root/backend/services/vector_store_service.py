"""
Simplified vector store service using ChromaDB for content storage and retrieval.
Supports caching of generated outlines for efficient retrieval.
"""
from chromadb import Client, Settings as ChromaSettings # Renamed to avoid conflict
from typing import Dict, List, Optional
from root.backend.models.embeddings.embedding_factory import EmbeddingFactory # Import the factory
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

            # Get the configured embedding function from the factory
            self.embedding_fn = EmbeddingFactory.get_embedding_function()
            logging.info(f"Using embedding function: {type(self.embedding_fn).__name__}")

            # Initialize ChromaDB Client
            self.client = Client(ChromaSettings( # Use renamed Settings
                persist_directory="root/data/vector_store",
                anonymized_telemetry=False,
                is_persistent=True
            ))

            # Get or create the collection, passing the embedding function instance
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
                                        
            # Store chunks with ordered IDs
            self.collection.add(
                documents=chunks,
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
                    where=where if where else None
                    # Removed limit=n_results when fetching by metadata only to ensure all chunks are retrieved
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
            
            # embeddings = [self.embedding_fn(chunk) for chunk in [outline_json]]
            
            # Store the outline as a single document - ChromaDB expects a list of documents
            # but the embedding function expects a single string
            self.collection.add(
                documents=[outline_json],  # Keep as a list with a single string
                metadatas=[metadata],
                ids=[f"outline_{cache_key}"],
                # embeddings=embeddings  # Skip embedding generation, let ChromaDB handle it
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


    # --- Section Cache Methods ---

    def store_section_cache(self, section_json: str, cache_key: str, project_name: str, outline_hash: str, section_index: int):
        """Store a generated section with metadata for caching.

        Args:
            section_json: The JSON string representation of the section (e.g., {"title": "...", "content": "..."})
            cache_key: A deterministic key (e.g., hash of project, outline_hash, index)
            project_name: The project name
            outline_hash: Hash representing the specific outline content.
            section_index: The index of the section within the outline.
        """
        try:
            metadata = {
                "content_type": "section_cache",
                "project_name": project_name,
                "outline_hash": outline_hash, # Use outline_hash instead of job_id
                "section_index": section_index,
                "cache_key": cache_key, # Store the key itself for potential lookup/debugging
                "timestamp": datetime.now().isoformat()
            }

            # Store the section JSON as a single document
            self.collection.add(
                documents=[section_json],
                metadatas=[metadata],
                ids=[f"section_{cache_key}"] # Unique ID based on the cache key
            )
            logging.info(f"Cached section {section_index} for outline {outline_hash} with key {cache_key}")
            return True
        except Exception as e:
            logging.error(f"Error caching section {section_index} for outline {outline_hash}: {e}")
            return False

    def retrieve_section_cache(self, cache_key: str, project_name: str, outline_hash: str, section_index: int) -> Optional[str]:
        """Retrieve a cached section based on its identifiers.

        Args:
            cache_key: The cache key to look up
            project_name: The project name
            outline_hash: Hash representing the specific outline content.
            section_index: The section index

        Returns:
            The cached section JSON string or None if not found
        """
        try:
            # Build the query filter using $and for precise matching
            where = {
                "$and": [
                    {"content_type": "section_cache"},
                    {"project_name": project_name},
                    {"outline_hash": outline_hash}, # Use outline_hash instead of job_id
                    {"section_index": section_index},
                    {"cache_key": cache_key} # Match the specific key
                ]
            }

            results = self.collection.get(
                where=where,
                limit=1
            )

            if results and results["documents"] and len(results["documents"]) > 0:
                logging.info(f"Found cached section {section_index} for outline {outline_hash} with key {cache_key}")
                return results["documents"][0]
            else:
                logging.info(f"No cached section found for outline {outline_hash}, section {section_index} with key {cache_key}")
                return None
        except Exception as e:
            logging.error(f"Error retrieving cached section {section_index} for outline {outline_hash}: {e}")
            return None

    def clear_section_cache(self, project_name: Optional[str] = None, outline_hash: Optional[str] = None):
        """Clear cached sections, optionally filtered by project and/or outline hash.

        Args:
            project_name: Optional project name to clear caches for
            outline_hash: Optional outline hash to clear caches for
        """
        try:
            filters = [{"content_type": "section_cache"}]
            if project_name:
                filters.append({"project_name": project_name})
            if outline_hash:
                filters.append({"outline_hash": outline_hash}) # Use outline_hash instead of job_id

            if len(filters) == 1: # Only content_type filter
                 where = filters[0]
            else:
                 where = {"$and": filters}

            self.collection.delete(where=where)

            log_msg = "Cleared section cache"
            if project_name: log_msg += f" for project {project_name}"
            if job_id: log_msg += f" for job {job_id}"
            logging.info(log_msg)

        except Exception as e:
            logging.error(f"Error clearing section cache: {e}")
