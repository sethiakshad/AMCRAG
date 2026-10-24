"""
Sparse Lexical Retrieval Engine using BM25Okapi with disk persistence.
"""
import re
import pickle
import os
from typing import List, Optional
from rank_bm25 import BM25Okapi

from schemas import DocumentChunk, ScoredCandidate


class BM25SparseEngine:
    def __init__(self, index_file_path: Optional[str] = "./bm25_index.pkl"):
        """
        Initializes the BM25 engine. Supports in-memory operation or disk loading.
        """
        self.index_file_path = index_file_path
        self.bm25: Optional[BM25Okapi] = None
        self.corpus_chunks: List[DocumentChunk] = []

        if index_file_path and os.path.exists(index_file_path):
            self.load_index(index_file_path)

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """
        Clean, lowercased alphanumeric tokenizer preserving alphanumeric symbols.
        Avoids heavy NLP library overhead while ensuring reliable keyword matching.
        """
        tokens = re.findall(r"\b[a-zA-Z0-9_\-\.]+\b", text.lower())
        return tokens

    def index_chunks(self, chunks: List[DocumentChunk], save_to_disk: bool = True):
        """
        Builds the BM25 inverted index from document chunks.
        """
        if not chunks:
            return

        self.corpus_chunks = chunks
        print(f"[SparseEngine] Tokenizing {len(chunks)} chunks for BM25...")
        tokenized_corpus = [self.tokenize(c.text) for c in chunks]

        # Initialize BM25Okapi (k1=1.5, b=0.75 are standard defaults)
        self.bm25 = BM25Okapi(tokenized_corpus, k1=1.5, b=0.75)
        print(f"[SparseEngine] BM25 Index constructed for {len(chunks)} chunks.")

        if save_to_disk and self.index_file_path:
            self.save_index(self.index_file_path)

    def search(
        self,
        query: str,
        top_k: int = 20,
        filters: Optional[dict] = None
    ) -> List[ScoredCandidate]:
        """
        Queries BM25 index and returns top_k scored candidates.
        Optionally filters candidates by metadata or chunk attributes.
        """
        if not self.bm25 or not self.corpus_chunks:
            return []

        tokenized_query = self.tokenize(query)
        if not tokenized_query:
            return []

        doc_scores = self.bm25.get_scores(tokenized_query)

        # Retrieve indices of sorted scoring items
        sorted_indices = sorted(
            range(len(doc_scores)),
            key=lambda idx: doc_scores[idx],
            reverse=True
        )

        candidates = []
        rank = 1
        for idx in sorted_indices:
            score = float(doc_scores[idx])
            if score <= 0.0:
                continue

            chunk = self.corpus_chunks[idx]

            # Apply metadata filters if provided
            if filters:
                match = True
                for fk, fv in filters.items():
                    val = getattr(chunk, fk, None)
                    if val is None and isinstance(chunk.metadata, dict):
                        val = chunk.metadata.get(fk)
                    if val != fv:
                        match = False
                        break
                if not match:
                    continue

            candidates.append(
                ScoredCandidate(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    page_number=chunk.page_number,
                    text=chunk.text,
                    source_filename=getattr(chunk, "source_filename", None),
                    page_start=getattr(chunk, "page_start", None),
                    page_end=getattr(chunk, "page_end", None),
                    score=score,
                    rank=rank,
                    metadata=chunk.metadata
                )
            )
            rank += 1
            if len(candidates) >= top_k:
                break

        return candidates

    def save_index(self, path: str):
        """Persists the BM25 model and corpus metadata to disk."""
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({"bm25": self.bm25, "corpus_chunks": self.corpus_chunks}, f)
        print(f"[SparseEngine] Index persisted to {path}")

    def load_index(self, path: str):
        """Loads a precomputed BM25 index and corpus chunks from disk."""
        with open(path, "rb") as f:
            data = pickle.load(f)
            self.bm25 = data["bm25"]
            self.corpus_chunks = data["corpus_chunks"]
        print(f"[SparseEngine] Loaded {len(self.corpus_chunks)} chunks from {path}")
