"""
Unit and integration tests for ChromaDB Vector Store.

Tests persistent caching, content hashing, cache invalidation,
and deterministic embedding retrieval for outcome mappings.
"""

import numpy as np
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

import ai.vector_store as vs
from ai.embeddings import compute_similarity_matrix_cached
from main import app


@pytest.fixture
def isolated_vector_store(tmp_path, monkeypatch):
    """Provide a fresh, isolated ChromaDB persistence directory for each test."""
    chroma_dir = str(tmp_path / "chroma_test")
    monkeypatch.setenv("CHROMA_PERSIST_DIR", chroma_dir)

    # Reset singletons
    vs._chroma_client = None
    vs._co_collection = None
    vs._fw_collection = None

    yield chroma_dir

    # Cleanup singletons
    vs._chroma_client = None
    vs._co_collection = None
    vs._fw_collection = None


def _dummy_embedding_fn(texts):
    """Deterministic dummy embedding function (length-based embedding for speed)."""
    dim = 16
    embeddings = []
    for text in texts:
        vec = np.zeros(dim, dtype=np.float32)
        for i, char in enumerate(text[:dim]):
            vec[i] = ord(char) / 255.0
        # Normalize
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        embeddings.append(vec)
    return np.array(embeddings, dtype=np.float32)


class TestVectorStoreCaching:
    """Test caching behavior and call counts."""

    def test_caching_skips_embedding_fn(self, isolated_vector_store):
        mock_embed = MagicMock(side_effect=_dummy_embedding_fn)

        subject_id = 42
        co_codes = ["CO1", "CO2"]
        texts = [
            "Apply sorting algorithms in software development",
            "Design database schemas for web applications",
        ]

        # First call: cache miss, must call mock_embed
        emb_first = vs.get_or_compute_co_embeddings(
            subject_id=subject_id,
            co_codes=co_codes,
            enhanced_texts=texts,
            embedding_fn=mock_embed,
        )

        assert mock_embed.call_count == 1
        assert emb_first.shape == (2, 16)

        # Second call with exact same inputs: cache hit, must NOT call mock_embed
        mock_embed.reset_mock()
        emb_second = vs.get_or_compute_co_embeddings(
            subject_id=subject_id,
            co_codes=co_codes,
            enhanced_texts=texts,
            embedding_fn=mock_embed,
        )

        assert mock_embed.call_count == 0
        np.testing.assert_allclose(emb_first, emb_second, atol=1e-5)

    def test_content_hash_detects_changes(self, isolated_vector_store):
        mock_embed = MagicMock(side_effect=_dummy_embedding_fn)

        subject_id = 10
        co_codes = ["CO1"]
        original_text = ["Original CO description text"]
        modified_text = ["Modified CO description text with updated words"]

        # Initial call
        vs.get_or_compute_co_embeddings(
            subject_id=subject_id,
            co_codes=co_codes,
            enhanced_texts=original_text,
            embedding_fn=mock_embed,
        )
        assert mock_embed.call_count == 1

        # Text modified: hash changes, triggers re-computation
        mock_embed.reset_mock()
        vs.get_or_compute_co_embeddings(
            subject_id=subject_id,
            co_codes=co_codes,
            enhanced_texts=modified_text,
            embedding_fn=mock_embed,
        )
        assert mock_embed.call_count == 1


class TestVectorStoreInvalidation:
    """Test invalidation functions."""

    def test_invalidate_co(self, isolated_vector_store):
        mock_embed = MagicMock(side_effect=_dummy_embedding_fn)

        subject_id = 1
        co_codes = ["CO1", "CO2"]
        texts = ["Text for CO1", "Text for CO2"]

        vs.get_or_compute_co_embeddings(subject_id, co_codes, texts, mock_embed)
        assert mock_embed.call_count == 1

        # Invalidate CO1 only
        vs.invalidate_co(subject_id, "CO1")

        # Next call: CO1 is miss (recomputed), CO2 is hit
        mock_embed.reset_mock()
        vs.get_or_compute_co_embeddings(subject_id, co_codes, texts, mock_embed)

        assert mock_embed.call_count == 1
        # Called with only CO1 text
        assert mock_embed.call_args[0][0] == ["Text for CO1"]

    def test_invalidate_subject(self, isolated_vector_store):
        mock_embed = MagicMock(side_effect=_dummy_embedding_fn)

        vs.get_or_compute_co_embeddings(100, ["CO1"], ["Subject 100 CO1"], mock_embed)
        vs.get_or_compute_co_embeddings(200, ["CO1"], ["Subject 200 CO1"], mock_embed)

        # Invalidate Subject 100
        vs.invalidate_subject(100)

        # Subject 100 must re-embed
        mock_embed.reset_mock()
        vs.get_or_compute_co_embeddings(100, ["CO1"], ["Subject 100 CO1"], mock_embed)
        assert mock_embed.call_count == 1

        # Subject 200 remains cached
        mock_embed.reset_mock()
        vs.get_or_compute_co_embeddings(200, ["CO1"], ["Subject 200 CO1"], mock_embed)
        assert mock_embed.call_count == 0

    def test_invalidate_framework(self, isolated_vector_store):
        mock_embed = MagicMock(side_effect=_dummy_embedding_fn)

        vs.get_or_compute_fw_embeddings(5, ["PO1", "PO2"], ["PO1 desc", "PO2 desc"], mock_embed)
        assert mock_embed.call_count == 1

        vs.invalidate_framework(5)

        mock_embed.reset_mock()
        vs.get_or_compute_fw_embeddings(5, ["PO1", "PO2"], ["PO1 desc", "PO2 desc"], mock_embed)
        assert mock_embed.call_count == 1


class TestVectorStoreStatsAndHealth:
    """Test metadata, stats, and health endpoint integration."""

    def test_stats_counts(self, isolated_vector_store):
        stats_initial = vs.get_vector_store_stats()
        assert stats_initial["vector_store"] == "chromadb"
        assert stats_initial["course_outcome_vectors"] == 0
        assert stats_initial["framework_outcome_vectors"] == 0

        vs.get_or_compute_co_embeddings(1, ["CO1"], ["CO 1 Text"], _dummy_embedding_fn)
        vs.get_or_compute_fw_embeddings(1, ["PO1"], ["PO 1 Text"], _dummy_embedding_fn)

        stats_after = vs.get_vector_store_stats()
        assert stats_after["course_outcome_vectors"] == 1
        assert stats_after["framework_outcome_vectors"] == 1

    def test_health_check_endpoint_includes_vector_store(self, isolated_vector_store):
        client = TestClient(app)
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert "vector_store" in data
        assert data["vector_store"]["vector_store"] == "chromadb"


class TestCachedSimilarityMatrix:
    """Test compute_similarity_matrix_cached integration."""

    def test_cached_similarity_shape_and_range(self, isolated_vector_store):
        co_texts = ["Apply data structures", "Analyze software performance"]
        po_texts = ["Engineering knowledge", "Problem analysis", "Design solutions"]

        # Uses tfidf fallback when model_name="tfidf"
        matrix_tfidf = compute_similarity_matrix_cached(
            co_texts, po_texts, subject_id=1, framework_id=1, model_name="tfidf"
        )
        assert matrix_tfidf.shape == (2, 3)
