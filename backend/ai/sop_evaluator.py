"""
backend/ai/sop_evaluator.py
============================
Statement of Purpose (SOP) / Motivation Letter Evaluator
using Hugging Face SentenceTransformer Embeddings + PyTorch

Architecture:
  1. Load SentenceTransformer (all-MiniLM-L6-v2) — a model specifically
     fine-tuned for semantic similarity via siamese network training.
     Unlike raw BERT [CLS], SentenceTransformer embeddings are designed
     to be directly compared with cosine similarity.
  2. Encode the student essay → 384-dimensional dense embedding vector
  3. Encode two anchor reference SOPs:
       - Strong SOP (academic, goal-oriented, research-specific language)
       - Weak SOP  (vague, generic, low-quality language)
  4. Compute cosine similarity between essay and both anchors:
       semantic_score = (sim_strong - sim_weak + 1) / 2  → [0, 1]
  5. Combine with NLP linguistic features (from scratch — no library):
       - Flesch Reading Ease (readability formula)
       - Type-Token Ratio (vocabulary diversity)
       - Academic keyword coverage
       - Word count score
  6. Weighted composite scoring formula
  7. Generate actionable, field-specific feedback tips

Note on design:
  This system is an NLP-based heuristic evaluator that combines
  Transformer embeddings with rule-based linguistic features.
  The weights (0.35, 0.20, 0.20, 0.15, 0.10) are manually set,
  not learned from labeled data. A future version with labeled SOP
  data and a supervised regression/classification model would be
  required to claim learned, data-driven weights.
"""

import re
import torch
import torch.nn.functional as F
from typing import Dict, Any, List


# ─────────────────────────────────────────────────────────────────────────────
# 1. SentenceTransformer Model Initialization
# ─────────────────────────────────────────────────────────────────────────────
# Using SentenceTransformer instead of raw BERT [CLS] because:
#   - BERT [CLS] is pre-trained for Masked LM & NSP, NOT similarity
#   - SentenceTransformer is fine-tuned with siamese networks on NLI & STS
#     datasets, making its embeddings meaningful for cosine similarity
#   - This is the same model already used in the RAG counselor module
try:
    from sentence_transformers import SentenceTransformer, util as st_util

    EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIM = 384

    print(f"Loading SentenceTransformer: {EMBEDDING_MODEL_NAME} ...")
    sentence_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    HAVE_SENTENCE_MODEL = True
    print(f"✅ [HuggingFace / SentenceTransformers] Loaded: {EMBEDDING_MODEL_NAME}")
    print(f"   Embedding dimension: {EMBEDDING_DIM}")

except Exception as e:
    HAVE_SENTENCE_MODEL = False
    sentence_model = None
    EMBEDDING_DIM = 384
    print(f"⚠️ [SentenceTransformer Load Warning]: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 2. Anchor Embedding References (for Cosine Similarity Scoring)
# ─────────────────────────────────────────────────────────────────────────────
# These serve as semantic quality benchmarks.
# The student essay embedding is compared against both anchors.
# A high-quality essay → high similarity to strong anchor, low to weak.
#
# Limitation (acknowledged): currently only 2 general references are used.
# A more robust system would maintain a labeled reference dataset
# organized by major (CS, Engineering, Business, Medicine, etc.).

STRONG_SOP_REFERENCE = """
I am applying for a Master of Science in Computer Science at Wuxi University
because I am deeply passionate about Artificial Intelligence research, specifically
large language model fine-tuning and computer vision. During my bachelor degree
I maintained a 4.9 GPA, led three research projects in deep learning, and published
a paper on transformer architectures. My long-term career goal is to establish an
AI research lab in Central Asia to advance machine learning education and contribute
to global scientific innovation. Studying in China aligns perfectly with this vision
due to the university faculty expertise and 100% scholarship support provided.
I have a clear academic background, a specific research focus, and a defined vision
for how this degree connects to my long-term professional contributions.
"""

WEAK_SOP_REFERENCE = """
I want to study abroad. I think it will be good for me. I like learning new things
and I hope to have a good future. I am a hard worker and I will do my best.
Please accept me to your university. Thank you.
"""

# Precompute anchor embeddings once at startup (cached in module scope)
_strong_anchor_embedding: torch.Tensor = None
_weak_anchor_embedding: torch.Tensor = None


def get_sentence_embedding(text: str) -> torch.Tensor:
    """
    Encodes text into a 384-dimensional dense embedding vector using
    SentenceTransformer (all-MiniLM-L6-v2).

    This model was specifically fine-tuned on Natural Language Inference (NLI)
    and Semantic Textual Similarity (STS) datasets using a siamese network
    architecture — making its embeddings meaningful for cosine similarity
    comparisons, unlike standard BERT [CLS] representations.

    Returns:
        embedding: FloatTensor of shape [384]
    """
    # SentenceTransformer handles tokenization + pooling internally
    # convert_to_tensor=True returns a PyTorch tensor directly
    embedding = sentence_model.encode(text, convert_to_tensor=True)
    return embedding  # shape: [384]


def get_anchor_embeddings():
    """Returns (or computes once) the cached anchor embeddings."""
    global _strong_anchor_embedding, _weak_anchor_embedding
    if _strong_anchor_embedding is None:
        _strong_anchor_embedding = get_sentence_embedding(STRONG_SOP_REFERENCE)
        _weak_anchor_embedding = get_sentence_embedding(WEAK_SOP_REFERENCE)
    return _strong_anchor_embedding, _weak_anchor_embedding


# ─────────────────────────────────────────────────────────────────────────────
# 3. Linguistic Feature Extractors (from scratch — no library)
# ─────────────────────────────────────────────────────────────────────────────

def calculate_flesch_reading_ease(text: str) -> float:
    """
    Flesch Reading Ease Score (implemented from mathematical formula).
    Range: 0 (very hard) → 100 (very easy). Academic essays target ~30-50.

    Formula:
        score = 206.835
                - 1.015  * (total_words / total_sentences)
                - 84.6   * (total_syllables / total_words)
    """
    words = re.findall(r'\w+', text)
    sentences = [s for s in re.split(r'[.!?]+', text) if s.strip()]

    word_count = max(len(words), 1)
    sentence_count = max(len(sentences), 1)

    syllable_count = sum(
        max(len(re.findall(r'[aeiouy]+', w.lower())), 1)
        for w in words
    )

    score = 206.835 - 1.015 * (word_count / sentence_count) - 84.6 * (syllable_count / word_count)
    return round(max(0.0, min(100.0, score)), 1)


def calculate_vocabulary_richness(words: List[str]) -> float:
    """
    Type-Token Ratio (TTR): unique_words / total_words.
    Higher = more diverse vocabulary.
    """
    if not words:
        return 0.0
    unique = set(w.lower() for w in words)
    return round((len(unique) / len(words)) * 100, 1)


# ─────────────────────────────────────────────────────────────────────────────
# 4. BERT Semantic Quality Scoring via Cosine Similarity
# ─────────────────────────────────────────────────────────────────────────────

def compute_semantic_quality(essay_embedding: torch.Tensor) -> Dict[str, Any]:
    """
    Computes semantic essay quality by comparing the student essay embedding
    against strong and weak anchor embeddings using cosine similarity.

    Scoring formula:
        raw_score  = cosine_sim(essay, strong_anchor) - cosine_sim(essay, weak_anchor)
        normalized = (raw_score + 1) / 2   → maps [-1, 1] into [0, 1]
        percentage = normalized * 100

    A well-written essay → high sim_strong, low sim_weak → raw_score near +1
    A weak essay         → low  sim_strong, high sim_weak → raw_score near -1

    Note: SentenceTransformer embeddings are calibrated for cosine similarity
    (trained on STS/NLI tasks), so these scores are semantically meaningful.
    """
    strong_anchor, weak_anchor = get_anchor_embeddings()

    # PyTorch cosine similarity: dot(a, b) / (||a|| * ||b||)
    sim_strong = float(F.cosine_similarity(
        essay_embedding.unsqueeze(0), strong_anchor.unsqueeze(0)
    ))
    sim_weak = float(F.cosine_similarity(
        essay_embedding.unsqueeze(0), weak_anchor.unsqueeze(0)
    ))

    raw_score = sim_strong - sim_weak           # ~ [-1, 1]
    normalized = (raw_score + 1.0) / 2.0       # → [0, 1]
    quality_percent = round(min(100.0, max(0.0, normalized * 100)), 1)

    return {
        "semantic_quality_score": quality_percent,
        "cosine_sim_strong": round(sim_strong, 4),
        "cosine_sim_weak": round(sim_weak, 4),
        "embedding_dim": essay_embedding.shape[0],
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5. Academic Keyword Coverage
# ─────────────────────────────────────────────────────────────────────────────

ACADEMIC_KEYWORDS = [
    "bachelor", "master", "degree", "university", "gpa", "research",
    "project", "internship", "thesis", "publication", "engineering",
    "data", "scholarship", "career", "goal", "aspire", "passionate",
    "faculty", "innovation", "leadership"
]


def keyword_coverage_score(text: str) -> float:
    """Returns 0–100 based on fraction of academic keywords present."""
    lowered = text.lower()
    matched = sum(1 for kw in ACADEMIC_KEYWORDS if kw in lowered)
    return round((matched / len(ACADEMIC_KEYWORDS)) * 100, 1)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Main SOP Evaluation Pipeline
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_sop_ai(
    sop_text: str,
    target_country: str = "General",
    target_major: str = "Computer Science"
) -> Dict[str, Any]:
    """
    Full SOP Evaluation Pipeline:

    Step 1  → Tokenize essay → BERT forward pass → [CLS] hidden state (768-dim)
    Step 2  → Cosine similarity vs. strong & weak anchor embeddings → semantic score
    Step 3  → Flesch Reading Ease score (readability)
    Step 4  → Type-Token Ratio (vocabulary richness)
    Step 5  → Academic keyword coverage
    Step 6  → Weighted composite overall score:
                overall = 0.40 * semantic_score   (BERT embedding quality)
                        + 0.20 * readability_norm  (Flesch normalized)
                        + 0.20 * keyword_coverage  (academic vocabulary)
                        + 0.20 * vocab_richness    (diversity)
    Step 7  → Generate actionable feedback tips
    """
    cleaned_text = sop_text.strip()
    words = re.findall(r'\b\w+\b', cleaned_text)
    word_count = len(words)

    # Guard: too short to evaluate meaningfully
    if word_count < 50:
        short_embedding = {
            "model": EMBEDDING_MODEL_NAME if HAVE_SENTENCE_MODEL else "Unavailable",
            "semantic_quality_score": 0.0,
            "cosine_sim_strong": 0.0,
            "cosine_sim_weak": 0.0,
            "embedding_dim": EMBEDDING_DIM,
            "semantic_assessment": "LOW",
            "semantic_score": 0.0,
        }
        return {
            "overall_score": 20,
            "verdict": "Too Short",
            "word_count": word_count,
            "readability_score": 0.0,
            "vocabulary_richness_percent": 0.0,
            "matched_keywords_count": 0,
            "embedding_analysis": short_embedding,
            "transformer_analysis": short_embedding,
            "bert_analysis": {
                "model": EMBEDDING_MODEL_NAME if HAVE_SENTENCE_MODEL else "Unavailable",
                "semantic_quality_score": 0.0,
                "cosine_sim_strong": 0.0,
                "cosine_sim_weak": 0.0,
                "bert_cls_dim": EMBEDDING_DIM,
            },
            "component_scores": {
                "semantic_quality": 20,
                "academic_background": 20,
                "motivation_and_fit": 20,
                "career_aspirations": 20,
                "language_and_clarity": 20,
                "word_length": 20,
            },
            "feedback": [
                "❌ Your essay is too short. A university SOP should be 400–800 words.",
                "📝 Describe your academic background, research experience, and career goals.",
            ]
        }

    # ── Step 1 & 2: BERT [CLS] Embedding + Cosine Similarity Scoring ──────────
    embedding_analysis = {
        "model": EMBEDDING_MODEL_NAME if HAVE_SENTENCE_MODEL else "Fallback (heuristic)",
        "semantic_quality_score": 55.0,
        "cosine_sim_strong": 0.55,
        "cosine_sim_weak": 0.45,
        "embedding_dim": EMBEDDING_DIM,
    }

    if HAVE_SENTENCE_MODEL:
        try:
            essay_embedding = get_sentence_embedding(cleaned_text)
            embedding_analysis = compute_semantic_quality(essay_embedding)
            embedding_analysis["model"] = EMBEDDING_MODEL_NAME
        except Exception as e:
            embedding_analysis["error"] = str(e)

    semantic_score = embedding_analysis["semantic_quality_score"]  # 0–100

    # ── Step 3: Flesch Reading Ease ────────────────────────────────────────────
    flesch_raw = calculate_flesch_reading_ease(cleaned_text)
    # Academic essays score 20–50 on Flesch — remap this range to 0–100
    # Flesch 50+ = too simple for academic writing, below 10 = too complex
    flesch_norm = round(min(100.0, max(0.0, (flesch_raw - 10.0) / 40.0 * 100)), 1)

    # ── Step 4: Vocabulary Richness (Type-Token Ratio) ─────────────────────────
    vocab_richness = calculate_vocabulary_richness(words)

    # ── Step 5: Academic Keyword Coverage ─────────────────────────────────────
    kw_coverage = keyword_coverage_score(cleaned_text)
    matched_kw_count = sum(1 for kw in ACADEMIC_KEYWORDS if kw in cleaned_text.lower())

    # ── Step 6: Word Length Score ──────────────────────────────────────────────
    # Optimal SOP: 400-800 words. Outside this range → penalty.
    if 400 <= word_count <= 800:
        length_score = 100.0
    elif 300 <= word_count < 400:
        length_score = 75.0
    elif 800 < word_count <= 1200:
        length_score = 85.0
    elif 200 <= word_count < 300:
        length_score = 55.0
    else:
        length_score = 30.0

    # ── Step 7: Weighted Composite Score ──────────────────────────────────────
    # BERT semantic similarity: 35% (primary semantic quality signal)
    # Word length:              20% (structural requirement)
    # Keyword coverage:         20% (academic domain coverage)
    # Readability:              15% (linguistic quality)
    # Vocabulary richness:      10% (language diversity)
    overall_score = round(
        0.35 * semantic_score +
        0.20 * length_score +
        0.20 * kw_coverage +
        0.15 * flesch_norm +
        0.10 * vocab_richness
    )
    overall_score = min(98, max(10, overall_score))  # clamp to [10, 98]

    # ── Component scores for radar chart in frontend ───────────────────────────
    # Motivation & Fit: check for country/university-specific mentions
    motivation_words = ["why", "chose", "specifically", "faculty",
                        "reputation", "campus", target_country.lower(),
                        target_major.lower()]
    motivation_score = 88 if any(w in cleaned_text.lower() for w in motivation_words) else 62

    # Career Aspirations: check for forward-looking language
    career_words = ["goal", "future", "aspire", "career",
                    "impact", "industry", "contribute", "vision"]
    career_score = 90 if any(w in cleaned_text.lower() for w in career_words) else 58

    component_scores = {
        "semantic_quality":    min(98, int(semantic_score)),
        "academic_background": min(98, int(kw_coverage * 0.6 + 40)),
        "motivation_and_fit":  motivation_score,
        "career_aspirations":  career_score,
        "language_and_clarity": min(98, int(flesch_norm * 0.5 + vocab_richness * 0.5)),
        "word_length":          min(98, int(length_score)),
    }

    # ── Step 8: Feedback Generation ───────────────────────────────────────────
    feedback = []

    if word_count < 400:
        feedback.append(f"💡 Your essay is {word_count} words. Aim for 500–750 words for a competitive SOP.")

    if semantic_score < 50:
        feedback.append(
            "🎯 Your essay's semantic content is below the expected quality threshold. "
            "Add specific research experience, academic achievements, and clear career goals."
        )
    elif semantic_score < 70:
        feedback.append(
            "📈 Good foundation, but strengthen the connection between your background and why "
            f"you are choosing to study {target_major} in {target_country}."
        )

    if motivation_score < 75:
        feedback.append(
            f"🏫 Be more specific about WHY you chose this university and what attracts "
            f"you to studying in {target_country}. Name specific faculty, labs, or programs."
        )

    if career_score < 70:
        feedback.append(
            "🚀 Add a dedicated paragraph on your 5-year career goal after graduation. "
            "Where do you see yourself and how does this degree help you get there?"
        )

    if vocab_richness < 40:
        feedback.append(
            "✍️ Your vocabulary diversity is low. Use varied academic transition phrases: "
            "'Furthermore', 'Consequently', 'This research demonstrated that...'"
        )

    if kw_coverage < 40:
        feedback.append(
            "📚 Include more academic terms: GPA, research project, thesis, internship, "
            "publication, or leadership experience."
        )

    if not feedback:
        feedback.append(
            "🌟 Excellent SOP! Your semantic content, vocabulary, and structure are "
            "all above the competitive threshold. Ready for submission."
        )

    verdict = (
        "Excellent — Ready for Submission" if overall_score >= 80
        else "Good — Minor Edits Recommended" if overall_score >= 60
        else "Needs Significant Improvement"
    )

    return {
        "overall_score": overall_score,
        "verdict": verdict,
        "word_count": word_count,
        "readability_score": flesch_raw,
        "vocabulary_richness_percent": vocab_richness,
        "matched_keywords_count": matched_kw_count,
        # ── Embedding Model Analysis ──────────────────────────────────────────
        # Renamed fields for technical accuracy (per reviewer feedback):
        #   - 'tone_sentiment'     removed (this is similarity, not sentiment analysis)
        #   - 'confidence_percent' renamed to 'semantic_score' (no probabilistic classifier)
        #   - 'bert_cls_dim'       renamed to 'embedding_dim'
        "embedding_analysis": {
            "model": embedding_analysis.get("model", EMBEDDING_MODEL_NAME),
            "semantic_quality_score": embedding_analysis.get("semantic_quality_score"),
            "cosine_sim_strong": embedding_analysis.get("cosine_sim_strong"),
            "cosine_sim_weak": embedding_analysis.get("cosine_sim_weak"),
            "embedding_dim": embedding_analysis.get("embedding_dim", EMBEDDING_DIM),
            "semantic_assessment": "HIGH" if semantic_score >= 60 else "MODERATE" if semantic_score >= 40 else "LOW",
            "semantic_score": round(semantic_score, 1),
        },
        # Backwards-compatibility aliases for frontend clients
        "transformer_analysis": {
            "model": embedding_analysis.get("model", EMBEDDING_MODEL_NAME),
            "semantic_quality_score": embedding_analysis.get("semantic_quality_score"),
            "confidence_percent": round(semantic_score, 1),
            "embedding_dim": embedding_analysis.get("embedding_dim", EMBEDDING_DIM),
        },
        "bert_analysis": {
            "model": embedding_analysis.get("model", EMBEDDING_MODEL_NAME),
            "semantic_quality_score": embedding_analysis.get("semantic_quality_score"),
            "cosine_sim_strong": embedding_analysis.get("cosine_sim_strong"),
            "cosine_sim_weak": embedding_analysis.get("cosine_sim_weak"),
            "bert_cls_dim": embedding_analysis.get("embedding_dim", EMBEDDING_DIM),
        },
        "component_scores": component_scores,
        "feedback": feedback,
    }
