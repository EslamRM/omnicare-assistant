"""
Policy retriever.

Embeddings: we use scikit-learn TF-IDF instead of Chroma's default
embedding function. Chroma's default downloads an ONNX model from the
network on first use, which is unnecessary setup risk and an unnecessary
dependency for a 2-section policy document. TF-IDF is zero-cost, needs no
network access, is fully deterministic, and is more than sufficient
retrieval quality for a corpus this small. Swapping in a real embedding
model later is a one-line change (see README "Production Evolution").

Vector store: Chroma (local, in-process, cosine similarity), used purely
as a similarity index over the precomputed TF-IDF vectors.
"""
import logging
from dataclasses import dataclass
from pathlib import Path

import chromadb
from sklearn.feature_extraction.text import TfidfVectorizer

from app.rag.ingest import load_and_chunk

# Chroma's telemetry call fails harmlessly against this posthog version
# (signature mismatch) and logs noise on every operation. It's caught
# internally and never affects behavior, so we just silence the logger.
logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)


@dataclass
class RetrievedChunk:
    text: str
    section: str
    score: float  # cosine similarity, higher is better


class PolicyRetriever:
    def __init__(self, policy_path: Path, chunk_size: int, chunk_overlap: int):
        self._chunks = load_and_chunk(policy_path, chunk_size, chunk_overlap)
        if not self._chunks:
            raise ValueError(f"No content extracted from {policy_path}")

        self._vectorizer = TfidfVectorizer()
        vectors = self._vectorizer.fit_transform([c.text for c in self._chunks]).toarray()

        # Fresh in-memory client each time — this is a prototype-scale
        # corpus, so we rebuild the index on process start rather than
        # persisting it to disk.
        client = chromadb.Client(chromadb.config.Settings(anonymized_telemetry=False))
        self._collection = client.get_or_create_collection(
            name="policy_chunks",
            metadata={"hnsw:space": "cosine"},
        )
        self._collection.add(
            ids=[c.chunk_id for c in self._chunks],
            embeddings=vectors.tolist(),
            documents=[c.text for c in self._chunks],
            metadatas=[{"section": c.section} for c in self._chunks],
        )

    def retrieve(self, query: str, top_k: int = 3) -> list[RetrievedChunk]:
        query_vec = self._vectorizer.transform([query]).toarray().tolist()
        results = self._collection.query(
            query_embeddings=query_vec,
            n_results=min(top_k, len(self._chunks)),
        )

        out = []
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        distances = results["distances"][0]  # cosine distance = 1 - cosine similarity
        for doc, meta, dist in zip(docs, metas, distances):
            similarity = 1 - dist
            out.append(RetrievedChunk(text=doc, section=meta["section"], score=similarity))
        return out
