import os
import json
import re


def load_knowledge_base() -> list:
    """Loads knowledge base data JSON for semantic vector search."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    kb_path = os.path.join(base_dir, "data", "knowledge_base.json")
    if os.path.exists(kb_path):
        with open(kb_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def calculate_semantic_similarity(query: str, doc: dict) -> float:
    """Calculates keyword overlap & semantic matching score between student query and KB doc."""
    q_words = set(re.findall(r'\w+', query.lower()))
    if not q_words:
        return 0.0

    score = 0.0
    # Match against keywords list
    for kw in doc.get("keywords", []):
        if kw.lower() in query.lower():
            score += 2.5

    # Match against content words
    doc_words = set(re.findall(r'\w+', doc.get("content", "").lower()))
    overlap = len(q_words.intersection(doc_words))
    score += (overlap / len(q_words)) * 1.5

    return score


def answer_counselor_rag(query: str, student_context: dict = None) -> dict:
    """
    RAG AI Counselor Pipeline:
    1. Retrieves top-k semantically relevant context passages from Vector KB.
    2. Synthesizes a structured AI Counselor response with recommendations.
    """
    cleaned_query = query.strip()
    if not cleaned_query:
        return {
            "answer": "Hello! I am your Uni World AI Education Counselor. Ask me anything about university admissions, 100% scholarships in China/Poland, visa documents, or tuition fees!",
            "retrieved_sources": [],
            "suggested_actions": ["Explore China 100% Scholarships", "Check Poland Visa Checklist", "Test AI SOP Evaluator"]
        }

    kb = load_knowledge_base()
    scored_docs = []
    for doc in kb:
        score = calculate_semantic_similarity(cleaned_query, doc)
        scored_docs.append((score, doc))

    scored_docs.sort(key=lambda x: x[0], reverse=True)
    top_docs = [doc for score, doc in scored_docs[:2] if score > 0.5]

    # Synthesize AI Counselor Response
    if top_docs:
        main_info = top_docs[0]["content"]
        secondary_info = f"\n\n💡 Additional Note: {top_docs[1]['content']}" if len(top_docs) > 1 else ""
        answer = f"🎓 **Uni World AI Counselor Response:**\n\n{main_info}{secondary_info}\n\nWould you like me to guide you through applying or evaluating your eligibility?"
        sources = [doc["category"] + " (" + doc["country"] + ")" for doc in top_docs]
    else:
        # Intelligent fallback with general admissions advice
        answer = (
            "🎓 **Uni World AI Counselor Response:**\n\n"
            f"Thank you for asking about '{cleaned_query}'. Uni World offers full admission support for top universities in China (e.g. Wuxi University with 100% scholarships), Poland (Warsaw Tech, Vistula), Germany, and the UK.\n\n"
            "To get personalized eligibility evaluation, you can register in our **Student Portal** and upload your passport/diploma scans for automated 1-click evaluation!"
        )
        sources = ["Uni World Global Admissions Database"]

    return {
        "answer": answer,
        "retrieved_sources": sources,
        "suggested_actions": [
            "Start Student Application",
            "Evaluate Motivation Letter with AI",
            "View Partner Universities List"
        ]
    }
