import os
import json
import numpy as np
import pdfplumber
import faiss
from sentence_transformers import SentenceTransformer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
RESUME_DIR = os.path.join(DATA_DIR, "resumes")
FAISS_INDEX_PATH = os.path.join(DATA_DIR, "resumes_faiss.index")
MAPPING_JSON_PATH = os.path.join(DATA_DIR, "resumes_mapping.json")

# Global variables for lazy loading
_model = None

def get_embedding_model():
    global _model
    if _model is None:
        print("Loading SentenceTransformer model ('all-MiniLM-L6-v2')...")
        # Load lightweight model for semantic matching
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
    except Exception as e:
        print(f"Error reading PDF {pdf_path}: {e}")
    return text.strip()

def build_resume_index():
    """Scan resumes, extract text, compute embeddings, and build the FAISS index."""
    if not os.path.exists(RESUME_DIR):
        print("Resume directory does not exist yet.")
        return False

    model = get_embedding_model()
    documents = []
    mapping = []
    
    # 1. Scan resumes directory
    for file_name in os.listdir(RESUME_DIR):
        if not file_name.endswith(".pdf"):
            continue
            
        file_path = os.path.join(RESUME_DIR, file_name)
        if not os.path.isfile(file_path):
            continue
            
        # Parse register number from the filename (e.g., CIT22CS001_resume_xxx.pdf or CIT22CS001_generated_resume.pdf)
        reg_no = file_name.split("_", 1)[0].strip()
        
        # Extract text content
        text = extract_text_from_pdf(file_path)
        if not text:
            print(f"Skipping empty or unreadable resume: {file_name}")
            continue
            
        documents.append(text)
        mapping.append({
            "register_number": reg_no,
            "filename": file_name
        })

    if not documents:
        print("No readable PDF resumes found to index.")
        # If mapping or index existed, remove them to keep state consistent
        if os.path.exists(FAISS_INDEX_PATH):
            os.remove(FAISS_INDEX_PATH)
        if os.path.exists(MAPPING_JSON_PATH):
            os.remove(MAPPING_JSON_PATH)
        return False

    # 2. Compute embeddings
    print(f"Computing semantic embeddings for {len(documents)} resumes...")
    embeddings = model.encode(documents, show_progress_bar=False)
    embeddings = np.array(embeddings).astype("float32")

    # 3. Create and populate FAISS index
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension) # Inner product (Cosine similarity if normalized)
    
    # Normalize vectors for cosine similarity search
    faiss.normalize_L2(embeddings)
    index.add(embeddings)

    # 4. Save to files
    faiss.write_index(index, FAISS_INDEX_PATH)
    with open(MAPPING_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2)

    print("Successfully built and saved FAISS index.")
    return True

def search_resumes(query_text, top_k=5):
    """Search FAISS index for resumes matching the query string."""
    if not os.path.exists(FAISS_INDEX_PATH) or not os.path.exists(MAPPING_JSON_PATH):
        # Index doesn't exist, try building it first
        built = build_resume_index()
        if not built:
            return []

    # Load mapping
    with open(MAPPING_JSON_PATH, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    # Load FAISS index
    index = faiss.read_index(FAISS_INDEX_PATH)

    # Encode query
    model = get_embedding_model()
    query_vector = model.encode([query_text])
    query_vector = np.array(query_vector).astype("float32")
    faiss.normalize_L2(query_vector)

    # Search
    k = min(top_k, len(mapping))
    if k <= 0:
        return []

    distances, indices = index.search(query_vector, k)

    # Compile results
    results = []
    for i, idx in enumerate(indices[0]):
        if idx == -1 or idx >= len(mapping):
            continue
        score = float(distances[0][i])
        
        # Scale score from [-1, 1] cosine similarity to [0, 100]%
        percentage_score = round((score + 1.0) / 2.0 * 100.0, 2)
        
        item = mapping[idx].copy()
        item["score"] = percentage_score
        results.append(item)

    return results
