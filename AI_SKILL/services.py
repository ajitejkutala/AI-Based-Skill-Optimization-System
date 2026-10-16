"""
Backend services for skill extraction, semantic matching, fit scores, gaps, and learning suggestions.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity


_MODEL_CACHE: dict[str, object] = {}


def _get_embedder(model_name: str):
    """Load SentenceTransformer if installed and functional, cached in memory."""
    if model_name in _MODEL_CACHE:
        return _MODEL_CACHE[model_name]
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(model_name)
        _MODEL_CACHE[model_name] = model
        return model
    except Exception as exc:
        print(f"[services] SentenceTransformer unavailable ({exc}). Using TF-IDF semantic matcher.")
        _MODEL_CACHE[model_name] = None
        return None


def _embedder(model_name: str):
    """Backwards-compatible alias for _get_embedder."""
    return _get_embedder(model_name)


def _tfidf_similarity(text1: str, text2: str) -> float:
    """Fast, lightweight fallback semantic similarity using scikit-learn TF-IDF."""
    t1 = (text1 or "").strip()
    t2 = (text2 or "").strip()
    if not t1 or not t2:
        return 0.0
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        vect = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        matrix = vect.fit_transform([t1, t2])
        sim = float(cosine_similarity(matrix[0:1], matrix[1:2])[0][0])
        return _clamp01(sim)
    except Exception:
        words1 = set(re.findall(r"\w+", t1.lower()))
        words2 = set(re.findall(r"\w+", t2.lower()))
        if not words1 or not words2:
            return 0.0
        return _clamp01(len(words1 & words2) / len(words1 | words2))


DEFAULT_SKILL_VOCAB = sorted(
    {
        "python",
        "java",
        "javascript",
        "typescript",
        "sql",
        "pandas",
        "numpy",
        "scikit-learn",
        "tensorflow",
        "pytorch",
        "nlp",
        "spacy",
        "nltk",
        "bert",
        "transformers",
        "machine learning",
        "deep learning",
        "data analysis",
        "data science",
        "statistics",
        "flask",
        "django",
        "fastapi",
        "rest api",
        "html",
        "css",
        "react",
        "docker",
        "kubernetes",
        "aws",
        "azure",
        "gcp",
        "git",
        "ci/cd",
        "project management",
        "communication",
        "leadership",
        "agile",
        "scrum",
    }
)


def extract_skills(text: str | None, skill_vocab: list[str] | None = None) -> list[str]:
    """
    Minimal NLP-style extraction:
    - normalize text
    - phrase/regex matches against a skill vocabulary
    """
    if not text:
        return []

    vocab = [s.lower() for s in (skill_vocab or DEFAULT_SKILL_VOCAB)]
    vocab_set = set(vocab)

    t = text.lower()
    t = re.sub(r"[\u2013\u2014]", "-", t)
    t = re.sub(r"\s+", " ", t).strip()

    found: set[str] = set()
    for skill in vocab:
        if skill in t:
            found.add(skill)

    if re.search(r"\bml\b", t):
        found.add("machine learning")
    if re.search(r"\bnlp\b", t):
        found.add("nlp")
    if re.search(r"\bci\s*/\s*cd\b", t) or re.search(r"\bcicd\b", t):
        found.add("ci/cd")

    return sorted(s for s in found if s in vocab_set)


def skills_from_json(skills_json: str | None) -> list[str]:
    """
    Parse skill JSON from legacy UIs: a dict of skill names (values ignored) or a list of names.
    """
    if not skills_json:
        return []
    try:
        obj = json.loads(skills_json)
        if isinstance(obj, list):
            skills = []
            for x in obj:
                if isinstance(x, str) and x.strip():
                    skills.append(x.strip().lower())
            return sorted(set(skills))
        if isinstance(obj, dict):
            skills = []
            for k in obj.keys():
                if isinstance(k, str) and k.strip():
                    skills.append(k.strip().lower())
            return sorted(set(skills))
        return []
    except Exception:
        return []

@dataclass(frozen=True)
class MatchResult:
    employee_id: int
    employee_name: str
    fit_percent: float
    matched_skills: list[str]
    missing_skills: list[str]
    explanation: str


def _cos(a: np.ndarray, b: np.ndarray) -> float:
    return float(cosine_similarity(a.reshape(1, -1), b.reshape(1, -1))[0][0])


def _clamp01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def compute_fit_percent(
    *,
    model_name: str,
    employee_text: str,
    employee_skills: list[str],
    job_text: str,
    required_skills: list[str],
    weight_semantic: float = 0.65,
    weight_overlap: float = 0.35,
) -> tuple[float, list[str], list[str], str]:
    """
    Returns:
    - fit_percent: single clean score shown in UI
    - matched_skills / missing_skills
    - explanation: simple text (no numeric breakdown)
    """
    emb = _get_embedder(model_name)
    semantic = 0.0
    if emb is not None:
        try:
            e_vec = np.asarray(emb.encode(employee_text or "", normalize_embeddings=True))
            j_vec = np.asarray(emb.encode(job_text or "", normalize_embeddings=True))
            semantic = _clamp01(max(0.0, _cos(e_vec, j_vec)))
        except Exception:
            semantic = _tfidf_similarity(employee_text, job_text)
    else:
        semantic = _tfidf_similarity(employee_text, job_text)

    emp_set = {s.strip().lower() for s in (employee_skills or []) if s and s.strip()}
    req_set = {s.strip().lower() for s in (required_skills or []) if s and s.strip()}

    matched = sorted(emp_set & req_set)
    missing = sorted(req_set - emp_set)

    overlap = (len(matched) / len(req_set)) if req_set else 0.0
    fit = _clamp01((weight_semantic * semantic) + (weight_overlap * overlap))

    fit_percent = round(fit * 100.0, 1)

    if req_set:
        explanation = (
            "Score is based on semantic similarity between the profile and job description, "
            "plus skill overlap with the required skills."
        )
    else:
        explanation = (
            "Score is based on semantic similarity between the profile and job description. "
            "Add required skills to enable gap analysis."
        )

    return fit_percent, matched, missing, explanation


def rank_employees(
    *,
    model_name: str,
    employees: list[dict],
    job: dict,
) -> list[MatchResult]:
    """
    employees: list of {id, full_name, title, resume_text, skills}
    job: {role_name, description, required_skills}
    """
    job_text = f"{job.get('role_name','')}\n\n{job.get('description','')}".strip()
    required = job.get("required_skills", []) or []

    out: list[MatchResult] = []
    for e in employees:
        employee_text = (
            f"{e.get('title','')}\n\n{e.get('resume_text','')}\n\nSkills: {', '.join(e.get('skills', []) or [])}"
        ).strip()

        fit_percent, matched, missing, explanation = compute_fit_percent(
            model_name=model_name,
            employee_text=employee_text,
            employee_skills=e.get("skills", []) or [],
            job_text=job_text,
            required_skills=required,
        )

        out.append(
            MatchResult(
                employee_id=int(e["id"]),
                employee_name=str(e.get("full_name", "")),
                fit_percent=fit_percent,
                matched_skills=matched,
                missing_skills=missing,
                explanation=explanation,
            )
        )

    out.sort(key=lambda r: r.fit_percent, reverse=True)
    return out


LEARNING_CATALOG: dict[str, list[dict[str, str]]] = {
    "python": [
        {"title": "Python for Everybody (Coursera)", "type": "course"},
        {"title": "PCAP – Certified Associate in Python Programming", "type": "cert"},
    ],
    "sql": [
        {"title": "SQL for Data Science (Coursera)", "type": "course"},
        {"title": "Microsoft DP-900: Azure Data Fundamentals", "type": "cert"},
    ],
    "machine learning": [
        {"title": "Machine Learning Specialization (DeepLearning.AI)", "type": "course"},
        {"title": "Google Professional Machine Learning Engineer", "type": "cert"},
    ],
    "nlp": [{"title": "Natural Language Processing Specialization (DeepLearning.AI)", "type": "course"}],
    "bert": [{"title": "Hugging Face Transformers Course", "type": "course"}],
    "docker": [
        {"title": "Docker Essentials (IBM)", "type": "course"},
        {"title": "Docker Certified Associate (DCA)", "type": "cert"},
    ],
    "aws": [
        {"title": "AWS Cloud Practitioner Essentials", "type": "course"},
        {"title": "AWS Certified Cloud Practitioner", "type": "cert"},
    ],
    "project management": [
        {"title": "Google Project Management (Coursera)", "type": "course"},
        {"title": "PMP – Project Management Professional", "type": "cert"},
    ],
}


def recommend_learning(missing_skills: list[str], max_items: int = 10) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[str] = set()

    for skill in (missing_skills or []):
        k = skill.strip().lower()
        for rec in LEARNING_CATALOG.get(k, []):
            sig = f"{rec.get('title','')}|{rec.get('type','')}"
            if sig in seen:
                continue
            seen.add(sig)
            items.append({"skill": k, **rec})
            if len(items) >= max_items:
                return items

    if not items and missing_skills:
        for s in missing_skills[: min(5, len(missing_skills))]:
            items.append({"skill": s, "title": f"Learning path for {s} (search courses/certs)", "type": "suggestion"})

    return items[:max_items]

