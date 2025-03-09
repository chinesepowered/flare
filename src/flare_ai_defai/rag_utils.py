import os
import json
from typing import List, Tuple
from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

def load_data(file_path: str) -> List[dict]:
    """
    Loads data from a JSON file.
    """
    with open(file_path, 'r') as f:
        data = json.load(f)
    return data

def create_chunks(data: List[dict], chunk_size: int = 200, chunk_overlap: int = 30) -> List[Tuple[str, dict]]:
    """
    Creates chunks from the loaded data.
    """
    chunks = []
    for item in data:
        text = item['text']
        metadata = item['metadata']
        
        # Split text into chunks
        text_chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size - chunk_overlap)]
        
        for chunk in text_chunks:
            chunks.append((chunk, metadata))
    return chunks

def embed_chunks(chunks: List[Tuple[str, dict]], model_name: str = 'all-mpnet-base-v2') -> List[Tuple[List[float], str, dict]]:
    """
    Embeds the created chunks using SentenceTransformer.
    """
    model = SentenceTransformer(model_name)
    embeddings = model.encode([chunk[0] for chunk in chunks])
    
    embedded_chunks = []
    for embedding, chunk in zip(embeddings, chunks):
        embedded_chunks.append((embedding.tolist(), chunk[0], chunk[1]))
    return embedded_chunks

def upload_to_qdrant(client: QdrantClient, collection_name: str, embedded_chunks: List[Tuple[List[float], str, dict]]):
    """
    Uploads the embedded chunks to Qdrant.
    """
    points = []
    for i, (embedding, chunk, metadata) in enumerate(embedded_chunks):
        payload = {
            "text": chunk,
            **metadata
        }
        point = models.PointStruct(
            id=i,
            vector=embedding,
            payload=payload
        )
        points.append(point)
    
    client.upsert(
        collection_name=collection_name,
        wait=True,
        points=points
    )
    print(f"Uploaded {len(points)} chunks to Qdrant collection '{collection_name}'.")

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