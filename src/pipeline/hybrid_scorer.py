"""
OmniScout-TG: Post-Level Hybrid RAG Scorer
Combines:
1. Pure-Python Okapi BM25 lexical matching on executive terms with negative penalties for student/exam terms.
2. Dense semantic embedding using local google/embeddinggemma-2 on NVIDIA RTX 4060 GPU (CUDA).
3. Reciprocal Rank Fusion (RRF) yielding a normalized Executive Fit Score (0–100).
Zero external b.ai API token consumption ($0).
"""

import json
import logging
import math
import os
import re
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

from src.models.schemas import CampaignBrief, ChannelEntity

logger = logging.getLogger(__name__)

# Standard executive positive terms for commercial/B2B/signature targeting
EXECUTIVE_POSITIVE_TERMS = [
    "امضا", "امضای", "قرارداد", "قراردادها", "قراردادهای", "مدیرعامل", "هیئت", "مدیره",
    "هیئت‌مدیره", "چک", "حقوقی", "صادرات", "واردات", "سرمایه", "سرمایه‌گذاری", "سرمایه گذاری",
    "بازرگانی", "شرکت", "شرکت‌ها", "هلدینگ", "سهامداران", "مناقصه", "مزایده", "رسمی", "مهر",
    "تجارت", "تعهدات", "بانکی", "کسب‌وکار", "کسب و کار", "مدیریت", "اتاق", "بازرگانی",
    "بورس", "سهام", "کارآفرین", "توسعه", "مشارکت"
]

# Student / Exam / Intern / Airdrop negative penalty terms (causes of Round 1 failure)
STUDENT_NEGATIVE_TERMS = [
    "دانشجو", "دانشجویان", "دانشجویی", "کنکور", "کارآموز", "کارآموزی", "پایان‌نامه",
    "پایان نامه", "جزوه", "امتحان", "ایردراپ", "همستر", "تپ‌سواپ", "داگز", "ارشد", "دکتری",
    "استخدام دانشجو", "پروژه دانشجویی", "آزمون وکالت", "تست زنی"
]


def tokenize_persian(text: str) -> list[str]:
    """Cleans and tokenizes Persian text into normalized terms."""
    if not text:
        return []
    # Normalize Arabic chars and zero-width spaces
    cleaned = (
        text.replace("ي", "ی")
        .replace("ك", "ک")
        .replace("\u200c", " ")
        .lower()
    )
    tokens = re.findall(r"[\u0600-\u06FF\w]{2,30}", cleaned)
    return tokens


class PureOkapiBM25:
    """Deterministic, pure-Python Okapi BM25 scoring with zero dependencies."""

    def __init__(self, corpus: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        self.doc_lens = [len(doc) for doc in corpus]
        self.avgdl = sum(self.doc_lens) / max(1, self.corpus_size)

        # Document frequencies
        self.df: dict[str, int] = Counter()
        self.doc_freqs: list[Counter] = []

        for doc in corpus:
            freq = Counter(doc)
            self.doc_freqs.append(freq)
            for token in freq.keys():
                self.df[token] += 1

        # Inverse document frequency
        self.idf: dict[str, float] = {}
        for token, freq in self.df.items():
            # Standard Lucene/Okapi smoothed IDF
            self.idf[token] = math.log(1.0 + (self.corpus_size - freq + 0.5) / (freq + 0.5))

    def score_document(self, doc_idx: int, query_tokens: list[str]) -> float:
        score = 0.0
        doc_freq = self.doc_freqs[doc_idx]
        doc_len = self.doc_lens[doc_idx]

        for q in query_tokens:
            if q not in doc_freq:
                continue
            tf = doc_freq[q]
            idf = self.idf.get(q, 0.0)
            numerator = tf * (self.k1 + 1.0)
            denominator = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / max(1.0, self.avgdl)))
            score += idf * (numerator / max(0.001, denominator))

        return score


def compute_tied_ranks(scores: list[float]) -> dict[int, float]:
    """Computes standard competition ranks handling ties identically."""
    indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    ranks: dict[int, float] = {}
    current_rank = 1
    for i, (orig_idx, score) in enumerate(indexed):
        if i > 0 and score < indexed[i - 1][1]:
            current_rank = i + 1
        ranks[orig_idx] = float(current_rank)
    return ranks


class HybridRAGScorer:
    """
    RAG-inspired hybrid scoring engine combining lexical BM25 and dense CUDA embeddings.
    Fuses rankings via Reciprocal Rank Fusion (RRF) with negative penalization.
    """

    def __init__(self, embedding_python_path: str | None = None):
        # Interpreter of the venv that hosts SentenceTransformers + EmbeddingGemma 2.
        # Override with EMBEDDING_PYTHON_PATH; without it, dense scores fall back to a baseline.
        self.embedding_python_path = embedding_python_path or os.environ.get(
            "EMBEDDING_PYTHON_PATH",
            r"C:\Users\Asus\.gemini\antigravity\scratch\embeddinggemma2\.venv\Scripts\python.exe",
        )
        self.embedding_runner_script = Path(__file__).parent / "embedding_runner.py"

    def score_channels(
        self,
        channels: list[ChannelEntity],
        brief: CampaignBrief,
    ) -> list[ChannelEntity]:
        """
        Executes BM25 and dense embedding scoring, and assigns executive_fit_score to each channel.
        """
        if not channels:
            return channels

        # 1. Prepare Document Texts
        doc_texts = []
        tokenized_corpus = []

        for ch in channels:
            # Combine title, bio, and sample recent post texts
            sample = ch.recent_posts_text_sample or ""
            doc_str = f"{ch.title} {ch.about or ''} {sample}"
            doc_texts.append(doc_str)
            tokenized_corpus.append(tokenize_persian(doc_str))

        # 2. Compute BM25 Lexical Scores with Negative Penalty
        bm25 = PureOkapiBM25(tokenized_corpus)
        bm25_net_scores: list[float] = []

        for i in range(len(channels)):
            pos_score = bm25.score_document(i, EXECUTIVE_POSITIVE_TERMS)
            neg_score = bm25.score_document(i, STUDENT_NEGATIVE_TERMS)

            # Heavy penalty multiplier for student/intern/exam keywords
            net_score = max(0.0, pos_score - (2.0 * neg_score))
            bm25_net_scores.append(round(net_score, 4))
            channels[i].bm25_score = round(net_score, 4)

        # 3. Compute Dense Embeddings via Local EmbeddingGemma 2 (CUDA)
        dense_scores = self._compute_dense_embeddings(doc_texts, brief)
        for i, ch in enumerate(channels):
            ch.dense_score = dense_scores[i] if i < len(dense_scores) else 0.5

        # 4. Reciprocal Rank Fusion (RRF) with Tied Ranking
        bm25_ranks = compute_tied_ranks(bm25_net_scores)
        dense_ranks = compute_tied_ranks(dense_scores)

        rrf_constant_k = 60
        rrf_raw: list[float] = []

        for i in range(len(channels)):
            r_b = bm25_ranks[i]
            r_d = dense_ranks[i]
            # Only reward BM25 rank if positive lexical matches were found
            bm25_rrf = (1.0 / (rrf_constant_k + r_b)) if bm25_net_scores[i] > 0 else 0.0
            dense_rrf = (1.0 / (rrf_constant_k + r_d)) if dense_scores[i] > 0 else 0.0
            rrf_raw.append(bm25_rrf + dense_rrf)

        # Normalize to 0 - 100 scale
        max_rrf = max(rrf_raw) if rrf_raw and max(rrf_raw) > 0 else 1.0

        for i, ch in enumerate(channels):
            if max_rrf > 0:
                scaled_score = (rrf_raw[i] / max_rrf) * 100.0
            else:
                scaled_score = 50.0

            # If document has higher negative student terms than positive executive terms, cap at 30
            doc_tokens = tokenized_corpus[i]
            pos_matches = sum(1 for t in doc_tokens if t in set(EXECUTIVE_POSITIVE_TERMS))
            neg_matches = sum(1 for t in doc_tokens if t in set(STUDENT_NEGATIVE_TERMS))

            if neg_matches > pos_matches and neg_matches >= 3:
                scaled_score = min(30.0, scaled_score * 0.4)
                logger.warning(f"Channel {ch.id} penalized due to {neg_matches} student/exam keyword matches.")

            ch.executive_fit_score = round(scaled_score, 1)

        logger.info(f"Hybrid RAG Scored {len(channels)} channels (Top Fit Score: {max(c.executive_fit_score for c in channels)}).")
        return channels

    def _compute_dense_embeddings(
        self,
        documents: list[str],
        brief: CampaignBrief,
    ) -> list[float]:
        """Invokes embedding_runner.py in the embeddinggemma2 venv on CUDA."""
        # Query representation emphasizing executive signature and official contracts
        query = (
            f"مدیران عامل، اعضای هیئت مدیره، تجار، کارآفرینان و سرمایه‌گذاران "
            f"که قراردادهای رسمی و حقوقی شرکت‌ها و اسناد تجاری و چک امضا می‌کنند. {brief.target_persona}"
        )

        input_payload = {
            "query": query,
            "documents": documents,
        }

        # Check if venv python exists
        if not os.path.exists(self.embedding_python_path):
            logger.warning(f"Embedding venv python not found at {self.embedding_python_path}. Falling back to baseline scores.")
            return [0.75 for _ in documents]

        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".json") as f:
                json.dump(input_payload, f, ensure_ascii=False)
                temp_input_path = f.name

            try:
                proc = subprocess.run(
                    [self.embedding_python_path, str(self.embedding_runner_script), temp_input_path],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=45.0,
                )

                if proc.returncode == 0 and proc.stdout.strip():
                    scores = json.loads(proc.stdout.strip())
                    if isinstance(scores, list) and len(scores) == len(documents):
                        return [float(s) for s in scores]
                else:
                    logger.error(f"Embedding runner failed (code {proc.returncode}): {proc.stderr}")
            finally:
                if os.path.exists(temp_input_path):
                    os.unlink(temp_input_path)

        except Exception as exc:
            logger.error(f"Failed to execute EmbeddingGemma 2 subprocess: {exc}")

        return [0.70 for _ in documents]
