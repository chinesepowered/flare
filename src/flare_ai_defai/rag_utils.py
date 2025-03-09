import os
import json
from typing import List, Tuple
from qdrant_client import QdrantClient, models
from flare_ai_defai.ai import GeminiEmbedding, EmbeddingTaskType
from flare_ai_defai.settings import settings
import hashlib

def load_data(file_path: str) -> List[dict]:
    """
    Loads data from a JSON file.
    """
    with open(file_path, 'r') as f:
        data = json.load(f)
    return data

def create_chunks(data: List[dict], chunk_size: int = 512) -> List[str]:
    """
    Splits the data into smaller chunks.
    """
    chunks = []
    for item in data:
        text = item['text']
        for i in range(0, len(text), chunk_size):
            chunks.append(text[i:i + chunk_size])
    return chunks

def embed_chunks(chunks: List[str]) -> List[Tuple[str, List[float]]]:
    """
    Embeds the chunks using Gemini Embedding.
    """
    # Initialize Gemini Embedding with the API key from settings
    # embedding_client = GeminiEmbedding(api_key=settings.gemini_api_key)
    
    embedded_chunks = []
    for chunk in chunks:
        # Embed the chunk using Gemini Embedding
        # embedding = embedding_client.embed_content(
        #     embedding_model="models/embedding-001",
        #     contents=chunk,
        #     task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT
        # )
        embedded_chunks.append((chunk, []))
    return embedded_chunks

def upload_to_qdrant(
    client: QdrantClient, collection_name: str, embedded_chunks: List[Tuple[str, List[float]]]
) -> None:
    """
    Uploads the embedded chunks to Qdrant.
    """
    points = []
    for i, (chunk, embedding) in enumerate(embedded_chunks):
        # Generate a unique ID for each point
        point_id = hashlib.sha256(chunk.encode()).hexdigest()
        points.append(
            models.PointStruct(
                id=point_id,
                vector=embedding,
                payload={"text": chunk},
            )
        )
    
    client.upsert(collection_name=collection_name, points=points, wait=True)

def create_collection(client: QdrantClient, collection_name: str) -> None:
    """
    Creates a collection in Qdrant.
    """
    client.recreate_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(size=1536, distance=models.Distance.COSINE),
    )

if __name__ == "__main__":
    # Example Usage
    from flare_ai_defai.qdrant_client import initialize_qdrant_client, create_collection
    
    # Initialize Qdrant client and create collection
    qdrant_client = initialize_qdrant_client()
    collection_name = "my_collection"
    create_collection(qdrant_client, collection_name)
    
    # Load data
    data = load_data('data.json')  # Replace 'data.json' with your data file
    
    # Create chunks
    chunks = create_chunks(data)
    
    # Embed chunks
    embedded_chunks = embed_chunks(chunks)
    
    # Upload to Qdrant
    upload_to_qdrant(qdrant_client, collection_name, embedded_chunks) 