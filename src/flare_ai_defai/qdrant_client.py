from collections.abc import Callable
from typing import Any
from qdrant_client import QdrantClient, models
from flare_ai_defai.settings import settings

def initialize_qdrant_client():
    """
    Initializes and returns a Qdrant client.
    
    This function creates an in-memory Qdrant instance when running in a container,
    or connects to an external Qdrant server based on settings.
    """
    # Use in-memory Qdrant when running in a container
    try:
        client = QdrantClient(
            location=":memory:",  # Use in-memory storage
        )
        print("Using in-memory Qdrant instance")
        
        # Create default collections
        create_collection(client, "semantic_cache")
        create_collection(client, "flare_knowledge")  # Create flare_knowledge collection
        return client
    except Exception as e:
        print(f"Failed to create in-memory Qdrant instance: {e}")
        
        # Fallback to URL-based connection
        try:
            client = QdrantClient(
                url=settings.qdrant_url,
                port=settings.qdrant_port,
                api_key=settings.qdrant_api_key,
                prefer_grpc=False,
            )
            print(f"Connected to Qdrant at {settings.qdrant_url}:{settings.qdrant_port}")
            
            # Create default collections
            create_collection(client, "semantic_cache")
            create_collection(client, "flare_knowledge")  # Create flare_knowledge collection
            return client
        except Exception as e:
            print(f"Failed to connect to Qdrant: {e}")
            
            # Return a dummy client that will no-op all operations
            return DummyQdrantClient()

def create_collection(client: QdrantClient, collection_name: str):
    """
    Creates a Qdrant collection if it does not exist.
    """
    try:
        client.get_collection(collection_name=collection_name)
        print(f"Collection '{collection_name}' already exists.")
    except Exception as e:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE),
        )
        print(f"Collection '{collection_name}' created successfully.")

class DummyQdrantClient:
    """
    A dummy Qdrant client that no-ops all operations.
    This is used as a fallback when Qdrant is not available.
    """
    def __getattr__(self, name: str) -> Callable[..., Any]:
        def noop_method(*args: Any, **kwargs: Any) -> list[Any] | None | Any:
            print(f"DummyQdrantClient: {name} called with args={args}, kwargs={kwargs}")
            # Return empty results for common operations
            if name == "search":
                return []
            elif name == "get_collection":
                return None
            elif name == "get_collections":
                class Collections:
                    def __init__(self) -> None:
                        self.collections: list[Any] = []
                return Collections()
            return None
        return noop_method

if __name__ == "__main__":
    # Example usage:
    qdrant_client = initialize_qdrant_client()
    create_collection(qdrant_client, "my_collection") 