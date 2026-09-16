"""
Embedding generation and semantic similarity computation.

Supports:
- sentence-transformers models (default: all-MiniLM-L6-v2)
- TF-IDF fallback for lightweight/no-torch environments

The embedding model is configurable via the EMBEDDING_MODEL env var.
"""

import os
import logging
import numpy as np
from typing import List, Optional
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

# Global model cache
_model_cache = {}


class EmbeddingProvider:
    """Base class for embedding providers."""

    def encode(self, texts: List[str]) -> np.ndarray:
        raise NotImplementedError


class SentenceTransformerProvider(EmbeddingProvider):
    """Embedding provider using sentence-transformers."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading sentence-transformer model: {self.model_name}")
                self._model = SentenceTransformer(self.model_name)
                logger.info("Model loaded successfully")
            except ImportError:
                raise ImportError(
                    "sentence-transformers is not installed. "
                    "Install with: pip install sentence-transformers"
                )
        return self._model

    def encode(self, texts: List[str]) -> np.ndarray:
        model = self._load_model()
        embeddings = model.encode(texts, show_progress_bar=False)
        return np.array(embeddings)


class TFIDFProvider(EmbeddingProvider):
    """
    Lightweight TF-IDF based embedding provider.
    Used as fallback when sentence-transformers is not available.
    """

    def __init__(self):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.vectorizer = TfidfVectorizer(
            max_features=500,
            stop_words='english',
            ngram_range=(1, 2)
        )
        self._fitted = False

    def encode(self, texts: List[str]) -> np.ndarray:
        if not self._fitted:
            matrix = self.vectorizer.fit_transform(texts)
            self._fitted = True
        else:
            matrix = self.vectorizer.transform(texts)
        return matrix.toarray()


def get_embedding_provider(model_name: Optional[str] = None) -> EmbeddingProvider:
    """
    Get the appropriate embedding provider based on configuration.

    Args:
        model_name: Override for the embedding model name.

    Returns:
        An EmbeddingProvider instance.
    """
    if model_name is None:
        model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    cache_key = model_name

    if cache_key not in _model_cache:
        if model_name == "tfidf":
            _model_cache[cache_key] = TFIDFProvider()
        else:
            try:
                _model_cache[cache_key] = SentenceTransformerProvider(model_name)
            except ImportError:
                logger.warning(
                    "sentence-transformers not available, falling back to TF-IDF"
                )
                _model_cache[cache_key] = TFIDFProvider()

    return _model_cache[cache_key]


def generate_embeddings(
    texts: List[str],
    model_name: Optional[str] = None
) -> np.ndarray:
    """
    Generate embeddings for a list of texts.

    Args:
        texts: List of text strings to embed.
        model_name: Optional model name override.

    Returns:
        numpy array of shape (n_texts, embedding_dim)
    """
    provider = get_embedding_provider(model_name)
    return provider.encode(texts)


def compute_similarity_matrix(
    co_texts: List[str],
    po_pso_texts: List[str],
    model_name: Optional[str] = None
) -> np.ndarray:
    """
    Compute pairwise cosine similarity between COs and POs/PSOs.

    Args:
        co_texts: List of CO text descriptions.
        po_pso_texts: List of PO/PSO text descriptions.
        model_name: Optional embedding model override.

    Returns:
        numpy array of shape (n_cos, n_pos_psos) with similarity scores.
    """
    # For TF-IDF, we need to fit on all texts together
    provider = get_embedding_provider(model_name)

    if isinstance(provider, TFIDFProvider):
        # Fit on combined texts, then separate
        all_texts = co_texts + po_pso_texts
        all_embeddings = provider.encode(all_texts)
        co_embeddings = all_embeddings[:len(co_texts)]
        po_pso_embeddings = all_embeddings[len(co_texts):]
    else:
        co_embeddings = provider.encode(co_texts)
        po_pso_embeddings = provider.encode(po_pso_texts)

    similarity = cosine_similarity(co_embeddings, po_pso_embeddings)
    return similarity


def compute_pairwise_similarity(
    text_a: str,
    text_b: str,
    model_name: Optional[str] = None
) -> float:
    """
    Compute cosine similarity between two individual texts.

    Returns:
        Float similarity score between -1 and 1.
    """
    provider = get_embedding_provider(model_name)

    if isinstance(provider, TFIDFProvider):
        embeddings = provider.encode([text_a, text_b])
        emb_a = embeddings[0:1]
        emb_b = embeddings[1:2]
    else:
        emb_a = provider.encode([text_a])
        emb_b = provider.encode([text_b])

    sim = cosine_similarity(emb_a, emb_b)
    return float(sim[0][0])
