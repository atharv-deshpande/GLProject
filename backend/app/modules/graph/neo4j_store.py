from __future__ import annotations

from typing import Any

from app.core.config import settings


class GraphStoreError(RuntimeError):
    """Raised when the optional Neo4j graph store is unavailable."""


class Neo4jGraphStore:
    """Optional derived graph adapter; PostgreSQL remains the authorization authority."""

    def __init__(self, uri: str | None = None, user: str | None = None,
                 password: str | None = None) -> None:
        self.uri = uri or settings.NEO4J_URI
        self.user = user or settings.NEO4J_USER
        self.password = password if password is not None else settings.NEO4J_PASSWORD

    def _driver(self):
        try:
            from neo4j import GraphDatabase
            return GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        except Exception as exc:
            raise GraphStoreError("Neo4j driver could not be initialized.") from exc

    def upsert_document_graph(self, document: dict[str, Any],
                              chunks: list[dict[str, Any]]) -> int:
        query = """
        MERGE (d:Department {id: $department_id})
        MERGE (doc:Document {id: $document_id})
        SET doc.title = $title, doc.filename = $filename
        MERGE (d)-[:OWNS]->(doc)
        WITH doc
        UNWIND $chunks AS item
          MERGE (c:Chunk {id: item.id})
          SET c.chunk_index = item.chunk_index, c.section_title = item.section_title
          MERGE (doc)-[:CONTAINS]->(c)
        RETURN count(c) AS stored
        """
        params = {
            "department_id": str(document["department_id"]),
            "document_id": str(document["document_id"]),
            "title": str(document.get("title") or ""),
            "filename": str(document.get("filename") or ""),
            "chunks": [
                {"id": str(row["id"]), "chunk_index": int(row["chunk_index"]),
                 "section_title": row.get("section_title")}
                for row in chunks
            ],
        }
        driver = self._driver()
        try:
            with driver.session() as session:
                result = session.run(query, params).single()
                return int(result["stored"]) if result else 0
        except Exception as exc:
            raise GraphStoreError("Neo4j document graph upsert failed.") from exc
        finally:
            driver.close()


    def delete_document_graph(self, document_id: str) -> None:
        """Idempotently remove a document and its derived chunk nodes."""
        query = """
        MATCH (doc:Document {id: $document_id})
        OPTIONAL MATCH (doc)-[:CONTAINS]->(chunk:Chunk)
        DETACH DELETE chunk, doc
        """
        driver = self._driver()
        try:
            with driver.session() as session:
                session.run(query, {"document_id": str(document_id)}).consume()
        except Exception as exc:
            raise GraphStoreError("Neo4j document graph deletion failed.") from exc
        finally:
            driver.close()
