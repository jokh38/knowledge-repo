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

logger = logging.getLogger(__name__)

# Configuration
VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH")
if not VAULT_PATH:
    raise ValueError("OBSIDIAN_VAULT_PATH environment variable not set")

DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")

# LLM Settings - Using Qwen3-Coder-30B model
Settings.llm = Ollama(
    model="Qwen3-Coder-30B",
    request_timeout=120.0,
    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
)

# Embedding Model - using lighter multilingual model
Settings.embed_model = HuggingFaceEmbedding(
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

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

    try:
        vector_store = get_vector_store()
        index = VectorStoreIndex.from_vector_store(vector_store)

        # Create query engine
        query_engine = index.as_query_engine(
            similarity_top_k=top_k,
            response_mode="compact"
        )

        response = query_engine.query(query_text)

        # Extract source information
        sources = []
        for node in response.source_nodes:
            source_info = {
                'file_path': node.metadata.get('file_name', 'Unknown'),
                'score': node.score if hasattr(node, 'score') else None,
                'content_preview': node.text[:200] + "..." if len(node.text) > 200 else node.text
            }
            sources.append(source_info)

        return {
            'answer': str(response),
            'sources': sources,
            'query': query_text
        }
    except Exception as e:
        logger.error(f"Error querying vault: {str(e)}")
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