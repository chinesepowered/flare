from qdrant_client import QdrantClient, models
from flare_ai_defai.settings import settings

def initialize_qdrant_client():
    """
    Initializes and returns a Qdrant client.
    """
    client = QdrantClient(
        url=settings.qdrant_url,
        port=settings.qdrant_port,
        api_key=settings.qdrant_api_key,
        https=True,  # Use HTTPS for secure connection
    )
    return client

def create_collection(client: QdrantClient, collection_name: str):
    """
    Creates a collection in Qdrant if it doesn't exist.
    """
    try:
        client.get_collection(collection_name=collection_name)
        print(f"Collection '{collection_name}' already exists.")
    except Exception as e:
        print(f"Creating collection '{collection_name}'...")
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(size=1536, distance=models.Distance.COSINE),
        )
        print(f"Collection '{collection_name}' created successfully.")

if __name__ == "__main__":
    # Example usage:
    qdrant_client = initialize_qdrant_client()
    create_collection(qdrant_client, "my_collection") 