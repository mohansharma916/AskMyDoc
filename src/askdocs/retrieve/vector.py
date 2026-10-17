"""Qdrant vector index. Point id == chunk_id; the payload carries everything a
citation needs (doc, file, page, section, text) so no second lookup is required."""

from dataclasses import dataclass

from qdrant_client import QdrantClient, models

from .types import Candidate

BATCH_SIZE = 128


def make_client(url: str) -> QdrantClient:
    if url == ":memory:":
        return QdrantClient(location=":memory:")
    if url.startswith(("http://", "https://")):
        return QdrantClient(url=url)
    return QdrantClient(path=url)  # embedded on-disk mode


@dataclass(frozen=True)
class VectorPoint:
    chunk_id: str
    vector: list[float]
    payload: dict


class QdrantIndex:
    def __init__(self, client: QdrantClient, collection: str, dim: int):
        self.client = client
        self.collection = collection
        self.dim = dim
        self._ensured = False

    def ensure_collection(self) -> None:
        if self._ensured:
            return
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                self.collection,
                vectors_config=models.VectorParams(size=self.dim, distance=models.Distance.COSINE),
            )
            self.client.create_payload_index(
                self.collection, field_name="doc_id", field_schema=models.PayloadSchemaType.KEYWORD
            )
        self._ensured = True

    def upsert(self, points: list[VectorPoint]) -> None:
        self.ensure_collection()
        for i in range(0, len(points), BATCH_SIZE):
            batch = points[i : i + BATCH_SIZE]
            self.client.upsert(
                self.collection,
                points=[models.PointStruct(id=p.chunk_id, vector=p.vector, payload=p.payload) for p in batch],
                wait=True,
            )

    def delete_document(self, doc_id: str) -> None:
        self.ensure_collection()
        self.client.delete(
            self.collection,
            points_selector=models.FilterSelector(filter=_doc_filter([doc_id])),
            wait=True,
        )

    def search(self, vector: list[float], k: int = 20, doc_ids: list[str] | None = None) -> list[Candidate]:
        self.ensure_collection()
        if doc_ids is not None and not doc_ids:
            return []
        response = self.client.query_points(
            self.collection,
            query=vector,
            limit=k,
            query_filter=_doc_filter(doc_ids) if doc_ids else None,
            with_payload=True,
        )
        return [
            Candidate(
                chunk_id=str(p.id),
                doc_id=p.payload["doc_id"],
                text=p.payload.get("text", ""),
                file_name=p.payload.get("file_name", ""),
                title=p.payload.get("title", ""),
                page=p.payload.get("page"),
                section_path=tuple(p.payload.get("section_path") or ()),
                scores={"vector": float(p.score)},
            )
            for p in response.points
        ]

    def count(self) -> int:
        self.ensure_collection()
        return self.client.count(self.collection, exact=True).count

    def ping(self) -> bool:
        try:
            self.client.get_collections()
            return True
        except Exception:
            return False


def _doc_filter(doc_ids: list[str]) -> models.Filter:
    return models.Filter(must=[models.FieldCondition(key="doc_id", match=models.MatchAny(any=doc_ids))])
