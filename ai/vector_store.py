"""
ChromaDB Vector Store — Persistent embedding cache for outcome texts.

Provides content-addressed caching of sentence-transformer embeddings so
that identical CO / PO / PSO descriptions are encoded exactly once.
Subsequent lookups return the stored vectors in O(1) time, guaranteeing
deterministic cosine similarity scores across repeated mapping runs.

Collections:
    - framework_outcomes: POs and PSOs keyed by (framework_id, outcome_code)
    - course_outcomes:    COs keyed by (subject_id, co_code)

Cache invalidation:
    Vectors are identified by a content hash (SHA-256 of the *enhanced* text).
    If a teacher edits an outcome description, the hash changes and the old
    vector is replaced automatically on the next mapping run.
"""

import hashlib
import logging
import os
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy singleton — avoids import-time side-effects and keeps the ChromaDB
# dependency optional for environments that don't use vector caching.
# ---------------------------------------------------------------------------

_chroma_client = None
_co_collection = None
_fw_collection = None


def _get_chroma_client():
    """Return (or create) the persistent ChromaDB client singleton."""
    global _chroma_client
    if _chroma_client is None:
        import chromadb

        persist_dir = os.getenv(
            "CHROMA_PERSIST_DIR",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "chroma_db"),
        )
        os.makedirs(persist_dir, exist_ok=True)

        _chroma_client = chromadb.PersistentClient(path=persist_dir)
        logger.info(f"ChromaDB persistent client initialised at: {persist_dir}")
    return _chroma_client


def _get_co_collection():
    """Collection for Course Outcome embeddings."""
    global _co_collection
    if _co_collection is None:
        client = _get_chroma_client()
        _co_collection = client.get_or_create_collection(
            name="course_outcomes",
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            f"ChromaDB collection 'course_outcomes' ready "
            f"({_co_collection.count()} vectors cached)"
        )
    return _co_collection


def _get_fw_collection():
    """Collection for Framework Outcome (PO / PSO) embeddings."""
    global _fw_collection
    if _fw_collection is None:
        client = _get_chroma_client()
        _fw_collection = client.get_or_create_collection(
            name="framework_outcomes",
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            f"ChromaDB collection 'framework_outcomes' ready "
            f"({_fw_collection.count()} vectors cached)"
        )
    return _fw_collection


# ---------------------------------------------------------------------------
# Content hashing
# ---------------------------------------------------------------------------

def _content_hash(text: str) -> str:
    """Return a deterministic SHA-256 hex digest of the text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_or_compute_co_embeddings(
    subject_id: int,
    co_codes: List[str],
    enhanced_texts: List[str],
    embedding_fn,
) -> np.ndarray:
    """
    Return CO embeddings, using the ChromaDB cache where possible.

    Args:
        subject_id:     Database subject ID.
        co_codes:       List of CO codes (e.g. ["CO1", "CO2", …]).
        enhanced_texts: Pre-processed / enhanced text for each CO.
        embedding_fn:   Callable(List[str]) -> np.ndarray  (shape N × D).

    Returns:
        np.ndarray of shape (len(co_codes), embedding_dim).
    """
    collection = _get_co_collection()
    return _get_or_compute(
        collection=collection,
        scope_key="subject",
        scope_id=subject_id,
        codes=co_codes,
        texts=enhanced_texts,
        embedding_fn=embedding_fn,
    )


def get_or_compute_fw_embeddings(
    framework_id: int,
    outcome_codes: List[str],
    enhanced_texts: List[str],
    embedding_fn,
) -> np.ndarray:
    """
    Return Framework Outcome (PO/PSO) embeddings, using cache where possible.

    Args:
        framework_id:   Database framework ID.
        outcome_codes:  List of outcome codes (e.g. ["PO1", …, "PSO1"]).
        enhanced_texts: Pre-processed / enhanced text for each outcome.
        embedding_fn:   Callable(List[str]) -> np.ndarray  (shape N × D).

    Returns:
        np.ndarray of shape (len(outcome_codes), embedding_dim).
    """
    collection = _get_fw_collection()
    return _get_or_compute(
        collection=collection,
        scope_key="framework",
        scope_id=framework_id,
        codes=outcome_codes,
        texts=enhanced_texts,
        embedding_fn=embedding_fn,
    )


def invalidate_co(subject_id: int, co_code: str) -> None:
    """Remove a single CO vector so it is re-computed on the next run."""
    collection = _get_co_collection()
    doc_id = f"subject_{subject_id}_{co_code}"
    try:
        collection.delete(ids=[doc_id])
        logger.info(f"Invalidated CO vector: {doc_id}")
    except Exception:
        pass  # Silently ignore if ID doesn't exist


def invalidate_subject(subject_id: int) -> None:
    """Remove all CO vectors for a subject (e.g. after syllabus re-upload)."""
    collection = _get_co_collection()
    try:
        collection.delete(where={"scope_id": int(subject_id)})
        logger.info(f"Invalidated CO vectors for subject {subject_id}")
    except Exception as e:
        logger.warning(f"Could not invalidate vectors for subject {subject_id}: {e}")


def invalidate_framework(framework_id: int) -> None:
    """Remove all PO/PSO vectors for a framework (e.g. after PO re-upload)."""
    collection = _get_fw_collection()
    try:
        collection.delete(where={"scope_id": int(framework_id)})
        logger.info(f"Invalidated framework vectors for framework {framework_id}")
    except Exception as e:
        logger.warning(
            f"Could not invalidate vectors for framework {framework_id}: {e}"
        )


def get_vector_store_stats() -> Dict:
    """Return a summary of the vector store for the health/config endpoint."""
    try:
        co_col = _get_co_collection()
        fw_col = _get_fw_collection()
        return {
            "vector_store": "chromadb",
            "persist_dir": os.getenv("CHROMA_PERSIST_DIR", "./chroma_db"),
            "course_outcome_vectors": co_col.count(),
            "framework_outcome_vectors": fw_col.count(),
        }
    except Exception as e:
        return {"vector_store": "chromadb", "error": str(e)}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_or_compute(
    collection,
    scope_key: str,
    scope_id: int,
    codes: List[str],
    texts: List[str],
    embedding_fn,
) -> np.ndarray:
    """
    Generic get-or-compute for a ChromaDB collection.

    For each (scope_id, code, text) triple:
        1. Build a deterministic document ID:  ``{scope_key}_{scope_id}_{code}``
        2. Check if that ID exists in the collection AND its stored content
           hash matches the current text.
        3. If yes  → use the cached embedding.
        4. If no   → compute the embedding via ``embedding_fn``, upsert it.

    Returns:
        np.ndarray of shape (len(codes), embedding_dim).
    """
    assert len(codes) == len(texts), "codes and texts must have the same length"

    doc_ids = [f"{scope_key}_{scope_id}_{code}" for code in codes]
    content_hashes = [_content_hash(t) for t in texts]

    # --- Fetch existing vectors in one batch call ---
    cached: Dict[str, Optional[List[float]]] = {}
    try:
        existing = collection.get(ids=doc_ids, include=["embeddings", "metadatas"])
        embeddings = existing.get("embeddings")
        metadatas = existing.get("metadatas")
        ids = existing.get("ids", [])
        if embeddings is not None and metadatas is not None:
            for idx, eid in enumerate(ids):
                stored_hash = (metadatas[idx] or {}).get("content_hash", "")
                pos = doc_ids.index(eid)
                emb = embeddings[idx]
                if stored_hash == content_hashes[pos] and emb is not None and len(emb) > 0:
                    cached[eid] = emb
    except Exception as e:
        logger.debug(f"ChromaDB cache lookup note: {e}")

    # --- Identify misses ---
    miss_indices = [i for i, did in enumerate(doc_ids) if did not in cached]

    cache_hits = len(codes) - len(miss_indices)
    if cache_hits:
        logger.info(
            f"Vector cache: {cache_hits}/{len(codes)} hits, "
            f"{len(miss_indices)} to compute"
        )

    # --- Compute missing embeddings in a single batch ---
    if miss_indices:
        miss_texts = [texts[i] for i in miss_indices]
        new_embeddings = embedding_fn(miss_texts)
        if not isinstance(new_embeddings, np.ndarray):
            new_embeddings = np.array(new_embeddings)

        # Upsert into ChromaDB
        upsert_ids = [doc_ids[i] for i in miss_indices]
        upsert_embeddings = new_embeddings.tolist()
        upsert_metadatas = [
            {
                "scope_key": scope_key,
                "scope_id": scope_id,
                "code": codes[i],
                "content_hash": content_hashes[i],
            }
            for i in miss_indices
        ]
        upsert_documents = [texts[i] for i in miss_indices]

        collection.upsert(
            ids=upsert_ids,
            embeddings=upsert_embeddings,
            metadatas=upsert_metadatas,
            documents=upsert_documents,
        )
        logger.info(f"Stored {len(miss_indices)} new vectors in ChromaDB")

        # Populate cache dict for assembly below
        for j, mi in enumerate(miss_indices):
            cached[doc_ids[mi]] = upsert_embeddings[j]

    # --- Assemble the result array in the original order ---
    result = np.array([cached[did] for did in doc_ids])
    return result
