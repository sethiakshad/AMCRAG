"""
Dense Embedding & Vector Retrieval Engine using BAAI/bge-base-en-v1.5 and Qdrant.
Owner: Om Khapekar
"""
import uuid
from typing import List, Optional
import torch
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from schemas import DocumentChunk, ScoredCandidate


class BGEDenseEngine:
    def __init__(
        self,
        model_name: str = "BAAI/bge-base-en-v1.5",
        collection_name: str = "amc_rag_text_chunks",
        qdrant_path: Optional[str] = "./qdrant_storage",
        qdrant_url: Optional[str] = None,
        qdrant_api_key: Optional[str] = None,
        device: Optional[str] = None,
    ):
        """
        Initializes BGE embedding model and Qdrant Vector DB connection.
        - If qdrant_url is provided, connects over HTTP/gRPC.
        - Otherwise, persists locally to `qdrant_path` or in-memory if qdrant_path is None.
        """
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        print(f"[DenseEngine] Loading {model_name} on {self.device}...")
        self.model = SentenceTransformer(model_name, device=self.device)
        self.collection_name = collection_name

        # Qdrant Client Setup (Local disk, Docker, or in-memory)
        if qdrant_url:
            self.client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
        elif qdrant_path:
            self.client = QdrantClient(path=qdrant_path)
        else:
            self.client = QdrantClient(location=":memory:")

        self._ensure_collection_exists()

    def _ensure_collection_exists(self):
        """Creates collection with Cosine distance if it doesn't already exist."""
        collections = [c.name for c in self.client.get_collections().collections]
        if self.collection_name not in collections:
            if hasattr(self.model, "get_embedding_dimension"):
                embedding_dim = self.model.get_embedding_dimension()
            else:
                embedding_dim = self.model.get_sentence_embedding_dimension()
            print(f"[DenseEngine] Creating Qdrant collection '{self.collection_name}' (dim={embedding_dim})")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=qmodels.VectorParams(
                    size=embedding_dim,
                    distance=qmodels.Distance.COSINE
                ),
                hnsw_config=qmodels.HnswConfigDiff(
                    m=16,
                    ef_construct=128
                )
            )

    def index_chunks(self, chunks: List[DocumentChunk], batch_size: int = 32):
        """
        Encodes document passages and upserts vectors + metadata into Qdrant.
        Note: BGE passages do NOT require an instruction prefix.
        """
        if not chunks:
            return

        texts = [chunk.text for chunk in chunks]
        print(f"[DenseEngine] Computing embeddings for {len(chunks)} chunks...")
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,
            normalize_embeddings=True,  # Crucial for Cosine similarity
            convert_to_numpy=True
        )

        points = []
        for chunk, emb in zip(chunks, embeddings):
            # Ensure deterministic point ID from UUID
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk.chunk_id))
            points.append(
                qmodels.PointStruct(
                    id=point_id,
                    vector=emb.tolist(),
                    payload={
                        "chunk_id": chunk.chunk_id,
                        "document_id": chunk.document_id,
                        "page_number": chunk.page_number,
                        "text": chunk.text,
                        "source_filename": getattr(chunk, "source_filename", None),
                        "page_start": getattr(chunk, "page_start", None),
                        "page_end": getattr(chunk, "page_end", None),
                        "metadata": chunk.metadata,
                    }
                )
            )

        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        print(f"[DenseEngine] Successfully indexed {len(points)} vectors in Qdrant.")

    def search(
        self,
        query: str,
        top_k: int = 20,
        filters: Optional[dict] = None
    ) -> List[ScoredCandidate]:
        """
        Encodes query with BGE search instruction and retrieves top_k nearest neighbors.
        Optionally applies metadata filters (e.g. document_id, page_number).
        """
        if not query or not query.strip():
            return []

        # BGE recommendation for asymmetric query retrieval:
        instructed_query = f"Represent this sentence for searching relevant passages: {query}"
        query_vector = self.model.encode(
            instructed_query,
            normalize_embeddings=True,
            convert_to_numpy=True
        ).tolist()

        # Build Qdrant filter if provided
        query_filter = None
        if filters:
            if isinstance(filters, qmodels.Filter):
                query_filter = filters
            elif isinstance(filters, dict):
                conditions = []
                for k, v in filters.items():
                    conditions.append(
                        qmodels.FieldCondition(
                            key=k,
                            match=qmodels.MatchValue(value=v)
                        )
                    )
                if conditions:
                    query_filter = qmodels.Filter(must=conditions)

        if hasattr(self.client, "query_points"):
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=top_k,
                search_params=qmodels.SearchParams(hnsw_ef=64)
            )
            search_results = response.points
        else:
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=top_k,
                search_params=qmodels.SearchParams(hnsw_ef=64)
            )

        candidates = []
        for rank, hit in enumerate(search_results, start=1):
            payload = hit.payload or {}
            candidates.append(
                ScoredCandidate(
                    chunk_id=payload.get("chunk_id", str(hit.id)),
                    document_id=payload.get("document_id", "unknown"),
                    page_number=payload.get("page_number", 0),
                    text=payload.get("text", ""),
                    source_filename=payload.get("source_filename"),
                    page_start=payload.get("page_start"),
                    page_end=payload.get("page_end"),
                    score=float(hit.score),
                    rank=rank,
                    metadata=payload.get("metadata", {})
                )
            )
        return candidates
