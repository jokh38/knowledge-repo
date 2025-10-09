from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.storage.storage_context import StorageContext
import chromadb
import os
from pathlib import Path
import logging
from typing import Dict, List, Optional
from utils.retry import retry
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

# Embedding Model - using lighter multilingual model
logger.debug(f"[DEBUG] Initializing embedding model")
try:
    Settings.embed_model = HuggingFaceEmbedding(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    logger.debug(f"[DEBUG] Embedding model initialized successfully")
except Exception as e:
    logger.error(f"[DEBUG] Failed to initialize primary embedding model: {str(e)}")
    logger.debug(f"[DEBUG] Trying fallback embedding model...")
    try:
        # Try a simpler model as fallback
        Settings.embed_model = HuggingFaceEmbedding(
            model_name="all-MiniLM-L6-v2"
        )
        logger.debug(f"[DEBUG] Fallback embedding model initialized successfully")
    except Exception as e2:
        logger.error(f"[DEBUG] All embedding models failed: {str(e2)}")
        raise Exception(f"Could not initialize any embedding model. Primary error: {str(e)}, Fallback error: {str(e2)}")

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
        query_engine = index.as_query_engine(
            similarity_top_k=top_k,
            response_mode="compact"
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

    try:
        vector_store = get_vector_store()
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        reader = SimpleDirectoryReader(input_files=[file_path])
        documents = reader.load_data()

        if not documents:
            logger.warning(f"No documents found in file: {file_path}")
            return

        index = VectorStoreIndex.from_vector_store(vector_store)
        for doc in documents:
            index.insert(doc)

        logger.info(f"Indexed new file: {file_path}")
    except Exception as e:
        logger.error(f"Error indexing file {file_path}: {str(e)}")
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