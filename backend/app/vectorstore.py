"""Weaviate access layer shared by every phase.

Vectors are computed client-side (see embeddings.py) and stored alongside the
text, so Weaviate's built-in BM25 index plus our vectors give us both pure
vector search (Phase 1) and native hybrid search (Phase 2) on one collection.
"""

import weaviate
from weaviate.classes.aggregate import GroupByAggregate
from weaviate.classes.config import Configure, DataType, Property
from weaviate.classes.query import Filter, MetadataQuery

from .config import get_settings
from .embeddings import get_embeddings

_client: weaviate.WeaviateClient | None = None


def get_client() -> weaviate.WeaviateClient:
    global _client
    if _client is None or not _client.is_connected():
        s = get_settings()
        _client = weaviate.connect_to_local(
            host=s.weaviate_host, port=s.weaviate_http_port, grpc_port=s.weaviate_grpc_port
        )
    return _client


def close_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


def is_ready() -> bool:
    try:
        return get_client().is_ready()
    except Exception:
        return False


def get_collection():
    client = get_client()
    name = get_settings().weaviate_collection
    if not client.collections.exists(name):
        client.collections.create(
            name,
            vectorizer_config=Configure.Vectorizer.none(),
            properties=[
                Property(name="text", data_type=DataType.TEXT),
                Property(name="source", data_type=DataType.TEXT, skip_vectorization=True),
                Property(name="page", data_type=DataType.INT),
                Property(name="chunk_index", data_type=DataType.INT),
            ],
        )
    return client.collections.get(name)


def add_chunks(chunks: list[dict]) -> int:
    if not chunks:
        return 0
    vectors = get_embeddings().embed_documents([c["text"] for c in chunks])
    collection = get_collection()
    with collection.batch.fixed_size(batch_size=100) as batch:
        for chunk, vector in zip(chunks, vectors):
            properties = {k: v for k, v in chunk.items() if v is not None}
            batch.add_object(properties=properties, vector=vector)
    failed = collection.batch.failed_objects
    if failed:
        raise RuntimeError(f"{len(failed)} chunks failed to insert: {failed[0].message}")
    return len(chunks)


def delete_source(source: str) -> None:
    get_collection().data.delete_many(where=Filter.by_property("source").equal(source))


def reset() -> None:
    client = get_client()
    name = get_settings().weaviate_collection
    if client.collections.exists(name):
        client.collections.delete(name)


def list_sources() -> list[dict]:
    response = get_collection().aggregate.over_all(
        group_by=GroupByAggregate(prop="source"), total_count=True
    )
    sources = [{"source": g.grouped_by.value, "chunks": g.total_count} for g in response.groups]
    return sorted(sources, key=lambda s: s["source"])


def _to_chunk(obj, score: float | None) -> dict:
    props = obj.properties
    return {
        "id": str(obj.uuid),
        "text": props["text"],
        "source": props["source"],
        "page": props.get("page"),
        "chunk_index": props.get("chunk_index"),
        "score": score,
    }


def vector_search(query: str, k: int) -> list[dict]:
    vector = get_embeddings().embed_query(query)
    response = get_collection().query.near_vector(
        near_vector=vector, limit=k, return_metadata=MetadataQuery(distance=True)
    )
    # Cosine distance -> similarity so higher is better everywhere in the UI.
    return [_to_chunk(o, round(1 - o.metadata.distance, 4)) for o in response.objects]


def hybrid_search(query: str, k: int, alpha: float) -> list[dict]:
    """BM25 + vector fused by Weaviate. alpha=0 is pure BM25, alpha=1 pure vector."""
    vector = get_embeddings().embed_query(query)
    response = get_collection().query.hybrid(
        query=query,
        vector=vector,
        alpha=alpha,
        limit=k,
        query_properties=["text"],
        return_metadata=MetadataQuery(score=True),
    )
    return [_to_chunk(o, round(o.metadata.score, 4)) for o in response.objects]
