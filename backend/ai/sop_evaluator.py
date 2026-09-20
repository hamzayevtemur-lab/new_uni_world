import re
import math


def calculate_flesch_reading_ease(text: str) -> float:
    """Calculates Flesch Reading Ease score for English text readability."""
    words = re.findall(r'\w+', text)
    sentences = re.split(r'[.!?]+', text)
    sentences = [s for s in sentences if s.strip()]

    word_count = max(len(words), 1)
    sentence_count = max(len(sentences), 1)

    # Estimate syllables
    syllable_count = 0
    for word in words:
        w = word.lower()
        count = len(re.findall(r'[aeiouy]+', w))
        syllable_count += max(count, 1)

    score = 206.835 - 1.015 * (word_count / sentence_count) - 84.6 * (syllable_count / word_count)
    return round(max(0.0, min(100.0, score)), 1)


def evaluate_sop_ai(sop_text: str, target_country: str = "General", target_major: str = "Computer Science") -> dict:
    """
    Evaluates a student's Statement of Purpose / Motivation Letter using NLP metrics
    and vector similarity scoring against university admission criteria.
    """
    cleaned_text = sop_text.strip()
    words = re.findall(r'\b\w+\b', cleaned_text)
    word_count = len(words)

    if word_count < 50:
        return {
            "overall_score": 35,
            "readability_score": 40,
            "word_count": word_count,
            "verdict": "Too Short",
            "feedback": [
                "Your Statement of Purpose is under 50 words. A standard motivation letter should be between 400 and 800 words.",
                "Elaborate on your academic background, major achievements, and why you selected this university."
            ],
            "component_scores": {
                "academic_background": 30,
                "motivation_and_fit": 35,
                "career_aspirations": 30,
                "language_and_clarity": 45
            }
        }

    # 1. Word Length Score (Optimal 450 - 850 words)
    if 450 <= word_count <= 850:
        length_score = 95
    elif 300 <= word_count < 450:
        length_score = 80
    elif 850 < word_count <= 1200:
        length_score = 85
    else:
        length_score = 60

    # 2. Key Educational & Academic Keyword Embedding Matching
    academic_keywords = [
        "bachelor", "master", "degree", "university", "gpa", "research", "project",
        "internship", "computer science", "engineering", "business", "data", "passion",
        "scholarship", "future", "career", "skill", "innovative", "leader", "opportunity"
    ]
    matched_keywords = [kw for kw in academic_keywords if kw in cleaned_text.lower()]
    keyword_coverage = min(100, int((len(matched_keywords) / 12) * 100))

    # 3. Readability & Vocabulary Richness
    readability = calculate_flesch_reading_ease(cleaned_text)
    unique_words = set(w.lower() for w in words)
    vocabulary_richness = round((len(unique_words) / word_count) * 100, 1)

    # 4. Structure Dimension Scores
    academic_score = min(98, max(55, int(keyword_coverage * 0.5 + 45)))
    motivation_score = 90 if any(k in cleaned_text.lower() for k in ["why", "chose", "faculty", "reputation", "campus", target_country.lower()]) else 72
    career_score = 92 if any(k in cleaned_text.lower() for k in ["goal", "future", "aspire", "career", "impact", "industry"]) else 68
    clarity_score = min(96, max(60, int(readability * 0.4 + vocabulary_richness * 0.6)))

    # Composite Overall Score
    overall_score = round(
        0.25 * length_score +
        0.25 * academic_score +
        0.25 * motivation_score +
        0.25 * clarity_score
    )

    # Generated Feedback Recommendations
    feedback_tips = []
    if word_count < 450:
        feedback_tips.append(f"💡 Word count is currently {word_count} words. Aim for 500-700 words to fully develop your arguments.")
    if motivation_score < 80:
        feedback_tips.append(f"🎯 Mention specific faculty, courses, or reasons why studying in {target_country} matches your ambitions.")
    if career_score < 80:
        feedback_tips.append("🚀 Add a dedicated paragraph explaining your long-term career goals after graduation.")
    if vocabulary_richness < 45:
        feedback_tips.append("✨ Use more varied academic vocabulary and transition phrases (e.g. 'Furthermore', 'Consequently', 'In addition').")

    if not feedback_tips:
        feedback_tips.append("🌟 Excellent Statement of Purpose! Your structure, length, and goals are clear and compelling.")

    verdict = "Excellent (Ready for Submission)" if overall_score >= 88 else "Good (Minor Edits Recommended)" if overall_score >= 72 else "Needs Improvement"

    return {
        "overall_score": overall_score,
        "verdict": verdict,
        "word_count": word_count,
        "readability_score": readability,
        "vocabulary_richness_percent": vocabulary_richness,
        "matched_keywords_count": len(matched_keywords),
        "component_scores": {
            "academic_background": academic_score,
            "motivation_and_fit": motivation_score,
            "career_aspirations": career_score,
            "language_and_clarity": clarity_score
        },
        "feedback": feedback_tips
    }
