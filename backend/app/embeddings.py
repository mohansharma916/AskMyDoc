from functools import lru_cache

from langchain_huggingface import HuggingFaceEmbeddings

from .config import get_settings


@lru_cache
def get_embeddings() -> HuggingFaceEmbeddings:
    """Local sentence-transformers model; loaded once on first use."""
    return HuggingFaceEmbeddings(
        model_name=get_settings().embedding_model,
        encode_kwargs={"normalize_embeddings": True},
    )
