from __future__ import annotations

import math
from typing import Sequence

import httpx

from app.core.config import settings


class EmbeddingServiceError(RuntimeError):
    """Raised when Ollama cannot produce valid embeddings."""


class OllamaEmbeddingService:
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_EMBEDDING_MODEL
        self.timeout = timeout or settings.OLLAMA_TIMEOUT_SECONDS

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        values = [text.strip() for text in texts]
        if not values or any(not value for value in values):
            raise ValueError("Embedding input must contain non-empty texts.")

        try:
            response = httpx.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": values},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            vectors = payload.get("embeddings")
        except (httpx.HTTPError, ValueError) as exc:
            raise EmbeddingServiceError(
                f"Ollama embedding request failed: {type(exc).__name__}"
            ) from exc

        if not isinstance(vectors, list) or len(vectors) != len(values):
            raise EmbeddingServiceError("Ollama returned an invalid embedding batch.")

        normalized: list[list[float]] = []
        dimension: int | None = None
        for vector in vectors:
            if not isinstance(vector, list) or not vector:
                raise EmbeddingServiceError("Ollama returned an empty embedding.")
            try:
                parsed = [float(number) for number in vector]
            except (TypeError, ValueError) as exc:
                raise EmbeddingServiceError("Embedding contains non-numeric values.") from exc
            if not all(math.isfinite(number) for number in parsed):
                raise EmbeddingServiceError("Embedding contains non-finite values.")
            if dimension is None:
                dimension = len(parsed)
            elif len(parsed) != dimension:
                raise EmbeddingServiceError("Embedding dimensions differ within a batch.")
            normalized.append(parsed)

        return normalized

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text])[0]
