import os
from dotenv import load_dotenv
import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

# Load variables
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

if not openai_api_key:
    print("ERROR: No OPENAI_API_KEY in .env")
    exit(1)

# Configure Chroma
client = chromadb.PersistentClient(path="./chroma_db")
embedding_fn = OpenAIEmbeddingFunction(
    api_key=openai_api_key,
    model_name="text-embedding-3-small"
)

# Create collection
col = client.get_or_create_collection(
    "day09_docs",
    embedding_function=embedding_fn,
    metadata={"hnsw:space": "cosine"}
)

docs_dir = "./data/docs"
doc_texts = []
doc_ids = []
doc_metas = []

for idx, fname in enumerate(os.listdir(docs_dir)):
    with open(os.path.join(docs_dir, fname), "r", encoding="utf-8") as f:
        content = f.read()
    
    doc_texts.append(content)
    doc_ids.append(f"doc_{idx}")
    doc_metas.append({"source": fname})

# Upsert effectively updates or adds
if doc_texts:
    col.upsert(
        documents=doc_texts,
        metadatas=doc_metas,
        ids=doc_ids
    )
    print(f"✅ Indexed {len(doc_texts)} documents with OpenAI embeddings.")
else:
    print("⚠️ No documents round in ./data/docs")
