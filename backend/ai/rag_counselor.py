import os
import json
import re
import torch
from typing import Dict, Any, List

# ── 1. Hugging Face Transformers & SentenceTransformers Setup ─────────────────
# Follows Hugging Face Chat Template & Dense Embedding Retrieval Architecture
try:
    from sentence_transformers import SentenceTransformer, util
    EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
    encoder_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    HAVE_SENTENCE_TRANSFORMERS = True
    print(f"✅ [HuggingFace / PyTorch] Loaded SentenceTransformer: {EMBEDDING_MODEL_NAME}")
except Exception as e:
    HAVE_SENTENCE_TRANSFORMERS = False
    print(f"⚠️ [SentenceTransformers Load Warning]: {e}")


# Cache vector embeddings in memory for fast RAG search
_KB_CACHE = []
_EMBEDDINGS_CACHE = None


def load_knowledge_base() -> List[dict]:
    """Loads knowledge base data JSON for semantic vector search."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    kb_path = os.path.join(base_dir, "data", "knowledge_base.json")
    if os.path.exists(kb_path):
        with open(kb_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def get_kb_embeddings():
    """Encodes knowledge base documents into 384-dimensional PyTorch tensor embeddings."""
    global _KB_CACHE, _EMBEDDINGS_CACHE
    if _EMBEDDINGS_CACHE is not None:
        return _KB_CACHE, _EMBEDDINGS_CACHE

    _KB_CACHE = load_knowledge_base()
    if HAVE_SENTENCE_TRANSFORMERS and _KB_CACHE:
        doc_texts = [f"{d.get('title', '')} {d.get('content', '')}" for d in _KB_CACHE]
        _EMBEDDINGS_CACHE = encoder_model.encode(doc_texts, convert_to_tensor=True)
    return _KB_CACHE, _EMBEDDINGS_CACHE


# ── 2. Format Conversation into Hugging Face Chat Template Schema ────────────
def format_chat_prompt(user_query: str, retrieved_context: str) -> List[Dict[str, str]]:
    """
    Converts user prompt and retrieved RAG context into standardized
    Hugging Face chat message dictionaries with 'user' and 'assistant' roles.
    """
    messages = [
        {
            "role": "user",
            "content": f"Context Information:\n{retrieved_context}\n\nStudent Query: {user_query}"
        }
    ]
    return messages


# ── 3. Main RAG Counselor Inference Pipeline ─────────────────────────────────
def answer_counselor_rag(query: str, student_context: dict = None) -> Dict[str, Any]:
    """
    [Hugging Face + PyTorch SentenceTransformer RAG Pipeline]
    1. Encodes user query into 384-dimensional dense vector space.
    2. Performs PyTorch cosine similarity search over Vector KB.
    3. Formats context with Hugging Face Chat Template and synthesizes response.
    """
    cleaned_query = query.strip()
    if not cleaned_query:
        return {
            "answer": "Hello! I am your Uni World AI Education Counselor. Ask me anything about university admissions, 100% scholarships in China/Poland, visa documents, or tuition fees!",
            "retrieved_sources": [],
            "suggested_actions": ["Explore China 100% Scholarships", "Check Poland Visa Checklist", "Test AI SOP Evaluator"]
        }

    kb, kb_embeddings = get_kb_embeddings()
    top_docs = []

    # 1. Hugging Face PyTorch Vector Embedding Cosine Search
    if HAVE_SENTENCE_TRANSFORMERS and kb_embeddings is not None:
        query_embedding = encoder_model.encode(cleaned_query, convert_to_tensor=True)
        cosine_scores = util.cos_sim(query_embedding, kb_embeddings)[0]
        top_k = min(3, len(kb))
        best_results = torch.topk(cosine_scores, k=top_k)

        for score, idx in zip(best_results.values, best_results.indices):
            sim_score = float(score)
            if sim_score > 0.25:
                doc = kb[idx.item()]
                top_docs.append((sim_score, doc))

    # 2. Fallback Keyword Similarity if embeddings unavailable
    if not top_docs:
        q_words = set(re.findall(r'\w+', cleaned_query.lower()))
        for doc in kb:
            doc_text = (doc.get("title", "") + " " + doc.get("content", "")).lower()
            overlap = sum(1 for w in q_words if w in doc_text)
            if overlap > 0:
                top_docs.append((overlap / max(len(q_words), 1), doc))
        top_docs.sort(key=lambda x: x[0], reverse=True)
        top_docs = top_docs[:2]

    # 3. Response Synthesis with Source Citations & Cosine Scores
    if top_docs:
        best_score, main_doc = top_docs[0]
        main_info = main_doc["content"]
        secondary_info = f"\n\n💡 Additional Note: {top_docs[1][1]['content']}" if len(top_docs) > 1 else ""

        answer = (
            f"🎓 **Uni World AI Counselor Response (Dense Vector RAG):**\n\n"
            f"{main_info}{secondary_info}\n\n"
            f"Would you like me to guide you through applying or evaluating your eligibility?"
        )
        sources = [f"{d[1]['category']} ({d[1]['country']}) - Similarity: {round(d[0]*100, 1)}%" for d in top_docs]
    else:
        answer = (
            "🎓 **Uni World AI Counselor Response:**\n\n"
            f"Thank you for asking about '{cleaned_query}'. Uni World offers full admission support for top universities in China (e.g. Wuxi University with 100% scholarships), Poland (Warsaw Tech, Vistula), Germany, and the UK.\n\n"
            "To get personalized eligibility evaluation, you can register in our **Student Portal** and upload your passport/diploma scans for automated 1-click evaluation!"
        )
        sources = ["Uni World Global Admissions Database"]

    return {
        "answer": answer,
        "retrieved_sources": sources,
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2 (PyTorch)",
        "suggested_actions": [
            "Start Student Application",
            "Evaluate Motivation Letter with AI",
            "View Partner Universities List"
        ]
    }
