"""Tests for the embedding module."""

import pytest
import numpy as np


class TestTFIDFProvider:
    """Test TF-IDF fallback (always available, no torch needed)."""

    def test_encode_returns_array(self):
        from ai.embeddings import TFIDFProvider
        provider = TFIDFProvider()
        texts = ["Apply sorting algorithms", "Engineering knowledge"]
        result = provider.encode(texts)
        assert isinstance(result, np.ndarray)
        assert result.shape[0] == 2

    def test_similarity_computation(self):
        from ai.embeddings import TFIDFProvider
        from sklearn.metrics.pairwise import cosine_similarity

        provider = TFIDFProvider()
        texts = [
            "Apply sorting algorithms and searching algorithms in programming language for efficient data processing",
            "Implement data structures algorithms programming for efficient problem solving using programming",
            "Ethics professional responsibility societal impact environmental sustainability cultural awareness legal norms",
        ]
        embeddings = provider.encode(texts)
        sim = cosine_similarity(embeddings)

        # First two texts share vocabulary (algorithms, programming, efficient),
        # third is about ethics — should be less similar to the first
        assert sim[0][1] > sim[0][2]


class TestComputeSimilarityMatrix:
    def test_matrix_shape(self):
        from ai.embeddings import compute_similarity_matrix

        co_texts = ["Apply algorithms", "Develop applications"]
        po_texts = ["Engineering knowledge", "Problem analysis", "Design solutions"]

        # Use tfidf for fast testing
        matrix = compute_similarity_matrix(co_texts, po_texts, model_name="tfidf")
        assert matrix.shape == (2, 3)

    def test_similarity_range(self):
        from ai.embeddings import compute_similarity_matrix

        co_texts = ["Apply and implement sorting algorithms"]
        po_texts = ["Engineering knowledge and fundamentals"]

        matrix = compute_similarity_matrix(co_texts, po_texts, model_name="tfidf")
        assert -1.0 <= matrix[0][0] <= 1.0


class TestSentenceTransformerProvider:
    """Test sentence-transformers (may be slow, marks as slow)."""

    @pytest.mark.slow
    def test_encode(self):
        from ai.embeddings import SentenceTransformerProvider
        provider = SentenceTransformerProvider("all-MiniLM-L6-v2")
        result = provider.encode(["Apply sorting algorithms"])
        assert isinstance(result, np.ndarray)
        assert result.shape == (1, 384)  # MiniLM produces 384-dim

    @pytest.mark.slow
    def test_similarity(self):
        from ai.embeddings import compute_similarity_matrix

        co_texts = ["Apply and implement sorting algorithms using C"]
        po_texts = ["Engineering knowledge", "Ethical responsibility"]

        matrix = compute_similarity_matrix(co_texts, po_texts, model_name="all-MiniLM-L6-v2")
        # "sorting algorithms" should be more related to "engineering knowledge"
        assert matrix[0][0] > matrix[0][1]
