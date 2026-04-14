"""
build_index.py — Build ChromaDB index from 5 internal documents.
Run: python build_index.py
"""

import os
import sys
import chromadb
from sentence_transformers import SentenceTransformer

# Fix Windows encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DOCS_DIR = "./data/docs"
CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "day09_docs"

CHUNK_SIZE = 500
CHUNK_OVERLAP = 100


def chunk_text(text, source, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Split text into overlapping chunks."""
    chunks = []
    paragraphs = text.split("\n\n")
    
    current_chunk = ""
    chunk_idx = 0
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        if len(current_chunk) + len(para) < chunk_size:
            current_chunk += ("\n\n" + para if current_chunk else para)
        else:
            if current_chunk:
                chunks.append({
                    "text": current_chunk.strip(),
                    "source": source,
                    "chunk_idx": chunk_idx,
                })
                chunk_idx += 1
                words = current_chunk.split()
                overlap_text = " ".join(words[-20:]) if len(words) > 20 else ""
                current_chunk = overlap_text + "\n\n" + para if overlap_text else para
            else:
                current_chunk = para
    
    if current_chunk.strip():
        chunks.append({
            "text": current_chunk.strip(),
            "source": source,
            "chunk_idx": chunk_idx,
        })
    
    return chunks


def build_index():
    """Build ChromaDB index from docs."""
    print("=" * 60)
    print("Building ChromaDB Index for Day 09 Lab")
    print("=" * 60)
    
    print("\nLoading embedding model...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    print("   Model loaded: all-MiniLM-L6-v2")
    
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    
    try:
        client.delete_collection(COLLECTION_NAME)
        print(f"   Deleted existing collection '{COLLECTION_NAME}'")
    except Exception:
        pass
    
    collection = client.get_or_create_collection(
        COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )
    
    all_chunks = []
    for fname in sorted(os.listdir(DOCS_DIR)):
        if not fname.endswith(".txt"):
            continue
        filepath = os.path.join(DOCS_DIR, fname)
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
        
        chunks = chunk_text(content, source=fname)
        all_chunks.extend(chunks)
        print(f"   {fname}: {len(chunks)} chunks")
    
    print(f"\nTotal chunks: {len(all_chunks)}")
    
    print("\nEmbedding chunks...")
    texts = [c["text"] for c in all_chunks]
    embeddings = model.encode(texts, show_progress_bar=False).tolist()
    
    ids = [f"chunk_{i:03d}" for i in range(len(all_chunks))]
    metadatas = [{"source": c["source"], "chunk_idx": c["chunk_idx"]} for c in all_chunks]
    
    collection.add(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    
    print(f"\nIndex built: {collection.count()} chunks in '{COLLECTION_NAME}'")
    
    # Test query
    print("\nTest query: 'SLA ticket P1'")
    test_embedding = model.encode(["SLA ticket P1"]).tolist()
    results = collection.query(
        query_embeddings=test_embedding,
        n_results=2,
        include=["documents", "distances", "metadatas"]
    )
    for i, (doc, dist, meta) in enumerate(zip(
        results["documents"][0],
        results["distances"][0],
        results["metadatas"][0]
    )):
        score = round(1 - dist, 4)
        print(f"   [{score}] {meta['source']}: {doc[:80]}...")
    
    print("\nChromaDB index ready.")


if __name__ == "__main__":
    build_index()
