from contextlib import asynccontextmanager
from typing import Literal

import anthropic
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import evaluation, ingestion, vectorstore
from .config import get_settings
from .graph import run_query
from .llm import LLMRefusal
from .prompts import load_prompts


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    vectorstore.close_client()


app = FastAPI(title="Multi-Phase RAG Demonstrator", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    question: str = Field(min_length=1)
    phase_target: Literal[1, 2, 3]


class EvaluateRequest(BaseModel):
    pipeline_phase: Literal[1, 2] = 2
    limit: int | None = Field(default=None, ge=1)


@app.get("/health")
def health():
    s = get_settings()
    return {
        "weaviate": vectorstore.is_ready(),
        "anthropic_key": bool(s.anthropic_api_key),
        "reranker": s.reranker,
        "cohere_key": bool(s.cohere_api_key),
        "llm_model": s.llm_model,
        "embedding_model": s.embedding_model,
    }


# --- Documents -----------------------------------------------------------------


@app.post("/upload")
def upload(files: list[UploadFile] = File(...)):
    results, errors = [], []
    for f in files:
        try:
            results.append(ingestion.ingest_file(f.filename, f.file.read()))
        except ValueError as exc:
            errors.append({"source": f.filename, "error": str(exc)})
    return {"ingested": results, "errors": errors, "documents": vectorstore.list_sources()}


@app.get("/documents")
def documents():
    return {"documents": vectorstore.list_sources()}


@app.delete("/documents/{source}")
def delete_document(source: str):
    vectorstore.delete_source(source)
    return {"documents": vectorstore.list_sources()}


@app.delete("/documents")
def reset_documents():
    vectorstore.reset()
    return {"documents": []}


# --- Query ---------------------------------------------------------------------


@app.post("/query")
def query(req: QueryRequest):
    try:
        return run_query(req.question.strip(), req.phase_target)
    except LLMRefusal as exc:
        raise HTTPException(422, f"The model declined to answer: {exc}")
    except anthropic.AuthenticationError:
        raise HTTPException(500, "Anthropic API key is missing or invalid. Set ANTHROPIC_API_KEY in backend/.env.")
    except anthropic.RateLimitError:
        raise HTTPException(429, "Anthropic rate limit hit. Try again shortly.")
    except anthropic.APIStatusError as exc:
        raise HTTPException(502, f"Anthropic API error ({exc.status_code}): {exc.message}")
    except anthropic.APIConnectionError:
        raise HTTPException(502, "Could not reach the Anthropic API.")
    except RuntimeError as exc:  # e.g. reranker misconfiguration
        raise HTTPException(500, str(exc))


@app.get("/prompts")
def prompts():
    return load_prompts()


# --- Evaluation (Phase 3) ------------------------------------------------------


@app.get("/golden")
def get_golden():
    items = evaluation.load_golden()
    return {"items": items, "warning": evaluation.golden_warning(len(items)) if items else None}


@app.post("/golden")
def upload_golden(file: UploadFile = File(...)):
    try:
        items = evaluation.parse_golden(file.filename, file.file.read())
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(400, f"Invalid golden dataset: {exc}")
    evaluation.save_golden(items)
    return {"items": items, "warning": evaluation.golden_warning(len(items))}


@app.post("/evaluate")
def start_evaluation(req: EvaluateRequest, background: BackgroundTasks):
    if not evaluation.load_golden():
        raise HTTPException(400, "Upload a golden dataset first.")
    job = evaluation.create_job(req.pipeline_phase, req.limit)
    background.add_task(evaluation.run_job, job["id"])
    return job


@app.get("/evaluate/history")
def evaluation_history():
    return {"builds": evaluation.load_history(), "thresholds": get_settings().thresholds}


@app.get("/evaluate/{job_id}")
def evaluation_status(job_id: str):
    job = evaluation.get_job(job_id)
    if job is None:
        raise HTTPException(404, "Unknown evaluation job.")
    return job
