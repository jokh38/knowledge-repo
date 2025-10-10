from dotenv import load_dotenv
load_dotenv()  # Load environment variables BEFORE importing llama_index modules

from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.storage.storage_context import StorageContext
import chromadb
import os
import time
from pathlib import Path
import logging
from typing import Dict, List, Optional
from src.retry import retry
from src.custom_llm import LlamaCppLLM

logger = logging.getLogger(__name__)

# Configuration
VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH")
if not VAULT_PATH:
    raise ValueError("OBSIDIAN_VAULT_PATH environment variable not set")

DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")

# LLM Settings - Using custom LLM for llama.cpp compatibility
base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
logger.debug(f"[DEBUG] Initializing LLM with base URL: {base_url}")
logger.debug(f"[DEBUG] Request timeout: 120.0s")

# Check if this is a llama.cpp server (port 8080) or standard Ollama (port 11434)
if base_url.endswith(":8080"):
    logger.debug(f"[DEBUG] Detected llama.cpp server, using custom LLM implementation")
    Settings.llm = LlamaCppLLM(
        model_name="Qwen3-Coder-30B-A3B-Instruct-UD-Q4_K_XL.gguf",
        base_url=base_url,
        temperature=0.3,
        timeout=120.0
    )
    logger.debug(f"[DEBUG] LlamaCppLLM initialized successfully")
else:
    logger.debug(f"[DEBUG] Detected standard Ollama server, using Ollama client")
    Settings.llm = Ollama(
        model="Qwen3-Coder-30B",
        request_timeout=120.0,
        base_url=base_url
    )
    logger.debug(f"[DEBUG] LlamaIndex Ollama LLM initialized successfully")

# Embedding Model - prioritize local embeddings
logger.debug(f"[DEBUG] Initializing embedding model")
try:
    # Suppress HuggingFace API warnings and debug logs
    import transformers
    transformers.logging.set_verbosity_error()

    # Get local model path from environment or use default
    local_model_path = os.getenv("EMBEDDING_MODEL_PATH")
    default_model_name = "all-MiniLM-L6-v2"

    # Check if local model path is provided and exists, otherwise fall back to model name
    if local_model_path and os.path.exists(local_model_path):
        logger.debug(f"[DEBUG] Using local embedding model at: {local_model_path}")
        Settings.embed_model = HuggingFaceEmbedding(
            model_name=local_model_path,
            embed_batch_size=1  # Process one at a time to reduce memory pressure
        )
    else:
        logger.debug(f"[DEBUG] Local model not found or not specified, using model name: {default_model_name}")
        # Suppress urllib3 debug logs for HuggingFace API calls
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        Settings.embed_model = HuggingFaceEmbedding(
            model_name=default_model_name,
            embed_batch_size=1  # Process one at a time to reduce memory pressure
        )
    logger.debug(f"[DEBUG] HuggingFace embedding model initialized successfully")
except Exception as e:
    logger.error(f"[DEBUG] Failed to initialize HuggingFace embedding model: {str(e)}")
    logger.debug(f"[DEBUG] Using simple mock embedding for testing...")
    # As a last resort, create a very simple mock embedding
    import numpy as np
    from typing import List
    from llama_index.core.embeddings import BaseEmbedding

    class SimpleMockEmbedding(BaseEmbedding):
        def _get_query_embedding(self, query: str) -> List[float]:
            # Simple hash-based embedding for testing
            import hashlib
            hash_obj = hashlib.md5(query.encode())
            hex_dig = hash_obj.hexdigest()
            # Convert to float array
            embedding = []
            for i in range(0, len(hex_dig), 2):
                byte_val = int(hex_dig[i:i+2], 16)
                embedding.append(byte_val / 255.0 - 0.5)  # Normalize to [-0.5, 0.5]
            # Pad or truncate to 384 dimensions
            while len(embedding) < 384:
                embedding.append(0.0)
            return embedding[:384]

        def _get_text_embedding(self, text: str) -> List[float]:
            return self._get_query_embedding(text)

        def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
            return [self._get_text_embedding(text) for text in texts]

        async def _aget_query_embedding(self, query: str) -> List[float]:
            return self._get_query_embedding(query)

        async def _aget_text_embedding(self, text: str) -> List[float]:
            return self._get_text_embedding(text)

        async def _aget_text_embeddings(self, texts: List[str]) -> List[List[float]]:
            return [self._get_text_embedding(text) for text in texts]

    Settings.embed_model = SimpleMockEmbedding()
    logger.debug(f"[DEBUG] Simple mock embedding initialized for testing")
    logger.debug(f"[DEBUG] Embedding model set to: {type(Settings.embed_model)}")

@retry(max_attempts=3, delay=2)
def get_vector_store():
    """Initialize ChromaDB vector store"""
    try:
        db = chromadb.PersistentClient(path=DB_PATH)
        collection = db.get_or_create_collection("obsidian_knowledge")
        vector_store = ChromaVectorStore(chroma_collection=collection)
        return vector_store
    except Exception as e:
        logger.error(f"Error initializing vector store: {str(e)}")
        raise

@retry(max_attempts=2, delay=5)
def index_vault(force_reindex: bool = False):
    """Index all markdown files in Obsidian vault"""

    vector_store = get_vector_store()
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    if force_reindex:
        # Clear existing index
        try:
            # Get collection and delete all documents
            collection = vector_store._collection
            collection.delete(where={})  # Delete all documents
            logger.info("Cleared existing index")
        except Exception as e:
            logger.warning(f"Failed to clear index: {e}")
            # Alternative: recreate collection
            db = chromadb.PersistentClient(path=DB_PATH)
            db.delete_collection("obsidian_knowledge")
            vector_store = get_vector_store()
            logger.info("Recreated collection")

    # Load all markdown files
    logger.info(f"Loading documents from {VAULT_PATH}")
    reader = SimpleDirectoryReader(
        input_dir=VAULT_PATH,
        recursive=True,
        required_exts=[".md"],
        exclude_hidden=True
    )

    documents = reader.load_data()
    logger.info(f"Loaded {len(documents)} documents")

    if not documents:
        logger.warning("No documents found to index")
        return None

    # Create index
    try:
        index = VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_context,
            show_progress=True
        )
        logger.info("Indexing complete")
        return index
    except Exception as e:
        logger.error(f"Error creating index: {str(e)}")
        raise

@retry(max_attempts=2, delay=1)
def query_vault(query_text: str, top_k: int = 5):
    """Query the indexed vault"""
    logger.debug(f"[DEBUG] Starting vault query")
    logger.debug(f"[DEBUG] Query text: {query_text}")
    logger.debug(f"[DEBUG] Top_k: {top_k}")

    try:
        logger.debug(f"[DEBUG] Getting vector store")
        vector_store = get_vector_store()
        logger.debug(f"[DEBUG] Creating VectorStoreIndex from vector store")
        index = VectorStoreIndex.from_vector_store(vector_store)

        # Create query engine
        logger.debug(f"[DEBUG] Creating query engine with similarity_top_k={top_k}, response_mode='compact'")
        logger.debug(f"[DEBUG] Using LLM: {type(Settings.llm)}")
        logger.debug(f"[DEBUG] LLM metadata: {Settings.llm.metadata}")
        query_engine = index.as_query_engine(
            similarity_top_k=top_k,
            response_mode="compact",
            llm=Settings.llm
        )
        logger.debug(f"[DEBUG] Query engine created successfully")

        logger.debug(f"[DEBUG] Executing query...")
        response = query_engine.query(query_text)
        logger.debug(f"[DEBUG] Query response received")
        logger.debug(f"[DEBUG] Response type: {type(response)}")
        logger.debug(f"[DEBUG] Response attributes: {dir(response)}")

        # Extract source information
        sources = []
        logger.debug(f"[DEBUG] Processing source nodes...")
        if hasattr(response, 'source_nodes'):
            logger.debug(f"[DEBUG] Found {len(response.source_nodes)} source nodes")
            for i, node in enumerate(response.source_nodes):
                logger.debug(f"[DEBUG] Processing source node {i+1}")
                logger.debug(f"[DEBUG] Node metadata: {node.metadata}")
                if hasattr(node, 'score'):
                    logger.debug(f"[DEBUG] Node score: {node.score}")
                logger.debug(f"[DEBUG] Node text length: {len(node.text)}")

                source_info = {
                    'file_path': node.metadata.get('file_name', 'Unknown'),
                    'score': node.score if hasattr(node, 'score') else None,
                    'content_preview': node.text[:200] + "..." if len(node.text) > 200 else node.text
                }
                sources.append(source_info)
        else:
            logger.debug(f"[DEBUG] No source_nodes attribute found in response")

        answer = str(response)
        logger.debug(f"[DEBUG] Final answer length: {len(answer)} characters")
        logger.debug(f"[DEBUG] Number of sources: {len(sources)}")

        return {
            'answer': answer,
            'sources': sources,
            'query': query_text
        }
    except Exception as e:
        logger.error(f"[DEBUG] Error querying vault: {str(e)}")
        logger.error(f"[DEBUG] Exception type: {type(e).__name__}")
        import traceback
        logger.debug(f"[DEBUG] Full traceback: {traceback.format_exc()}")
        raise

@retry(max_attempts=2, delay=1)
def incremental_index(file_path: str):
    """Index a single file (for new captures)"""
    index_start = time.time()
    logger.info(f"[INDEXER] Starting incremental indexing for: {file_path}")

    try:
        logger.debug(f"[INDEXER] Step 1: Getting vector store")
        vector_store_start = time.time()
        vector_store = get_vector_store()
        vector_store_duration = time.time() - vector_store_start
        logger.debug(f"[INDEXER] Vector store obtained in {vector_store_duration:.2f}s")

        logger.debug(f"[INDEXER] Step 2: Creating storage context")
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        logger.debug(f"[INDEXER] Step 3: Loading documents from file")
        reader_start = time.time()
        reader = SimpleDirectoryReader(input_files=[file_path])
        documents = reader.load_data()
        reader_duration = time.time() - reader_start
        logger.debug(f"[INDEXER] Documents loaded in {reader_duration:.2f}s: {len(documents)} docs")

        if not documents:
            logger.warning(f"[INDEXER] No documents found in file: {file_path}")
            return

        logger.debug(f"[INDEXER] Step 4: Creating index from vector store")
        index_creation_start = time.time()
        index = VectorStoreIndex.from_vector_store(vector_store)
        index_creation_duration = time.time() - index_creation_start
        logger.debug(f"[INDEXER] Index created in {index_creation_duration:.2f}s")

        logger.debug(f"[INDEXER] Step 5: Inserting documents into index")
        insert_start = time.time()
        for i, doc in enumerate(documents):
            logger.debug(f"[INDEXER] Inserting document {i+1}/{len(documents)}")
            index.insert(doc)
        insert_duration = time.time() - insert_start
        logger.debug(f"[INDEXER] Documents inserted in {insert_duration:.2f}s")

        total_duration = time.time() - index_start
        logger.info(f"[INDEXER] Successfully indexed file {file_path} in {total_duration:.2f}s")

    except Exception as e:
        total_duration = time.time() - index_start
        logger.error(f"[INDEXER] Indexing failed after {total_duration:.2f}s: {type(e).__name__}: {str(e)}")

        # Detailed network error analysis
        error_str = str(e).lower()
        if "connection" in error_str or "network" in error_str:
            logger.error(f"[INDEXER] Network connection error during indexing: {e}")
        elif "timeout" in error_str:
            logger.error(f"[INDEXER] Timeout error during indexing: {e}")
        elif "context_window" in error_str:
            logger.error(f"[INDEXER] LLM metadata error during indexing: {e}")

        import traceback
        logger.error(f"[INDEXER] Indexing error traceback: {traceback.format_exc()}")
        raise

def remove_from_index(file_path: str):
    """Remove a file from the index"""
    try:
        vector_store = get_vector_store()
        collection = vector_store._collection
        
        # Find documents by file path
        results = collection.get(
            where={"file_name": os.path.basename(file_path)}
        )
        
        if results['ids']:
            collection.delete(ids=results['ids'])
            logger.info(f"Removed {len(results['ids'])} documents from index: {file_path}")
        else:
            logger.warning(f"No documents found for file: {file_path}")
    except Exception as e:
        logger.error(f"Error removing file from index {file_path}: {str(e)}")
        raise

def get_index_stats():
    """Get statistics about the index"""
    try:
        vector_store = get_vector_store()
        collection = vector_store._collection
        
        count = collection.count()
        
        return {
            'total_documents': count,
            'collection_name': collection.name,
            'db_path': DB_PATH
        }
    except Exception as e:
        logger.error(f"Error getting index stats: {str(e)}")
        return {}

def search_by_file_pattern(pattern: str, top_k: int = 10):
    """Search for documents matching a file pattern"""
    try:
        vector_store = get_vector_store()
        collection = vector_store._collection
        
        # This is a simple implementation - in practice, you might want more sophisticated matching
        results = collection.get(
            where={"file_name": {"$regex": pattern}}
        )
        
        return {
            'documents': results['documents'][:top_k],
            'metadatas': results['metadatas'][:top_k],
            'count': len(results['documents'])
        }
    except Exception as e:
        logger.error(f"Error searching by pattern: {str(e)}")
        return {}