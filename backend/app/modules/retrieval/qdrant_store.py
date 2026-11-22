from __future__ import annotations

from typing import Any, Sequence
from uuid import UUID

import httpx

from app.core.config import settings


class VectorStoreError(RuntimeError):
    """Raised when Qdrant indexing or retrieval fails."""


class QdrantVectorStore:
    """Small Qdrant REST adapter; vectors are indexed with department metadata."""

    def __init__(
        self,
        url: str | None = None,
        collection: str | None = None,
        api_key: str | None = None,
        timeout: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = (url or settings.QDRANT_URL).rstrip("/")
        self.collection = collection or settings.QDRANT_COLLECTION
        key = api_key if api_key is not None else settings.QDRANT_API_KEY
        headers = {"api-key": key} if key else {}
        self.client = client or httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=timeout,
        )

    def ensure_collection(self, vector_size: int) -> None:
        try:
            response = self.client.get(f"/collections/{self.collection}")
            if response.status_code == 404:
                created = self.client.put(
                    f"/collections/{self.collection}",
                    json={
                        "vectors": {
                            "size": vector_size,
                            "distance": "Cosine",
                        }
                    },
                )
                created.raise_for_status()
                exists = False
            else:
                response.raise_for_status()
                exists = True

            if exists:
                vectors = response.json()["result"]["config"]["params"]["vectors"]
                if not isinstance(vectors, dict) or "size" not in vectors:
                    raise VectorStoreError(
                        "Named-vector Qdrant collections are not supported."
                    )
                if int(vectors["size"]) != vector_size:
                    raise VectorStoreError(
                        f"Qdrant vector size mismatch: collection={vectors['size']}, "
                        f"embedding={vector_size}. Use a new collection when changing "
                        "embedding models."
                    )

            # A keyword payload index makes department filters efficient.
            index_response = self.client.put(
                f"/collections/{self.collection}/index",
                json={"field_name": "department_id", "field_schema": "keyword"},
            )
            if index_response.status_code not in (200, 409):
                index_response.raise_for_status()

        except VectorStoreError:
            raise
        except httpx.HTTPError as exc:
            raise VectorStoreError("Unable to initialize Qdrant collection.") from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise VectorStoreError("Qdrant collection configuration is invalid.") from exc

    def upsert_chunks(
        self,
        rows: Sequence[dict[str, Any]],
        vectors: Sequence[list[float]],
    ) -> None:
        if len(rows) != len(vectors):
            raise ValueError("Each chunk must have exactly one vector.")
        if not rows:
            return

        self.ensure_collection(len(vectors[0]))
        points = []
        for row, vector in zip(rows, vectors):
            points.append({
                "id": str(row["chunk_id"]),
                "vector": vector,
                "payload": {
                    "document_id": str(row["document_id"]),
                    "department_id": str(row["department_id"]),
                    "version_id": str(row["version_id"]),
                    "chunk_index": int(row["chunk_index"]),
                    "page_number": row.get("page_number"),
                    "section_title": row.get("section_title"),
                    "document_name": row["document_name"],
                },
            })

        try:
            response = self.client.put(
                f"/collections/{self.collection}/points",
                params={"wait": "true"},
                json={"points": points},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise VectorStoreError("Unable to upsert document vectors into Qdrant.") from exc

    def search(
        self,
        vector: list[float],
        department_ids: Sequence[UUID],
        limit: int,
    ) -> list[dict[str, Any]]:
        if not department_ids:
            return []
        try:
            response = self.client.post(
                f"/collections/{self.collection}/points/query",
                json={
                    "query": vector,
                    "filter": {
                        "must": [{
                            "key": "department_id",
                            "match": {"any": [str(value) for value in department_ids]},
                        }]
                    },
                    "limit": limit,
                    "with_payload": True,
                    "with_vector": False,
                },
            )
            response.raise_for_status()
            points = response.json().get("result", {}).get("points", [])
            return [
                {
                    "chunk_id": point["id"],
                    "score": float(point["score"]),
                    "payload": point.get("payload") or {},
                }
                for point in points
            ]
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise VectorStoreError("Qdrant semantic search failed.") from exc
