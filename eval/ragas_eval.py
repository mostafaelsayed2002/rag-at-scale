"""RAGAS scores on the golden set, in two steps.

    answer: ask every question through the app and save the answers
    score:  give the saved answers to RAGAS as one dataset (Gemini is the judge)

    uv run --project api --group eval python eval/ragas_eval.py answer
    uv run --project api --group eval python eval/ragas_eval.py score

The answer step skips questions already answered, so after a quota stop just
run it again.
"""

# remove and fix all the warnings
import logging, warnings

warnings.filterwarnings("ignore")  # the Python warnings
logging.getLogger("google_genai").setLevel(logging.ERROR)  # the AFC note


import asyncio
import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

# ragas 0.4.3 imports a Vertex AI class that no longer exists in
# langchain-community. We don't use it, so an empty stand-in is enough.
vertexai = types.ModuleType("langchain_community.chat_models.vertexai")
vertexai.ChatVertexAI = type("ChatVertexAI", (), {})
sys.modules[vertexai.__name__] = vertexai

from langsmith import tracing_context
from ragas import EvaluationDataset, RunConfig, evaluate
from langchain_core.embeddings import Embeddings
from ragas.metrics import (
    Faithfulness,
    LLMContextPrecisionWithReference,
    LLMContextRecall,
    ResponseRelevancy,
)

from app.core.config import settings
from app.db.pool import pool
from app.rag.embedder import build_embedder, embed_query
from app.rag.generator import answer_question, build_llm
from app.rag.retriever import retrieve

GOLDEN = ROOT / "eval" / "golden.jsonl"
ANSWERS = ROOT / "eval" / "results" / "answers.jsonl"
SCORES = ROOT / "eval" / "results" / "scores.csv"


def read(path: Path) -> list[dict]:
    """Read a .jsonl file (empty list if it does not exist yet)."""
    if not path.exists():
        return []
    with path.open() as f:
        return [json.loads(line) for line in f]


def append(path: Path, row: dict) -> None:
    """Save one line immediately, so nothing is lost if the run stops."""
    path.parent.mkdir(exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(row) + "\n")


async def answer() -> None:
    """Step 1: answer every golden question the way the app does."""
    done = {row["id"] for row in read(ANSWERS)}
    questions = [q for q in read(GOLDEN) if q["id"] not in done]

    await pool.open()
    embedder = build_embedder()
    llm = build_llm()

    with tracing_context(enabled=False):  # keep eval runs out of LangSmith
        for q in questions:
            print(q["id"], q["question"])
            vector = await embed_query(embedder, q["question"])
            chunks = await retrieve(vector, settings.retrieve_k)
            result = await answer_question(llm, q["question"], chunks)
            # Saved with RAGAS's field names, so the score step can pass the
            # lines straight to RAGAS (it ignores "id" and "answerable").
            append(
                ANSWERS,
                {
                    "id": q["id"],
                    "answerable": q["answerable"],
                    "user_input": q["question"],
                    "response": result.text,
                    "retrieved_contexts": [chunk["text"] for chunk in chunks],
                    "reference": q["answer"],
                },
            )

    await pool.close()


class BgeEmbeddings(Embeddings):
    """The app's bge model with the two methods RAGAS's answer relevancy calls.
    Local, so it costs no API calls."""

    def __init__(self):
        self.encoder = build_embedder()  # not "model": ragas reads that as a name

    def embed_query(self, text: str) -> list[float]:
        return self.encoder.encode(text, normalize_embeddings=True).tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.encoder.encode(texts, normalize_embeddings=True).tolist()


def score(limit: int | None = None) -> None:
    """Step 2: give RAGAS the saved answers as one dataset and let it score them.

    limit: score only the first N answers, to test cheaply before a full run.
    """
    # Only answerable questions: the others have no reference answer.
    rows = [r for r in read(ANSWERS) if r["answerable"]][:limit]
    dataset = EvaluationDataset.from_list(rows)

    result = evaluate(
        dataset,
        metrics=[
            Faithfulness(),
            # strictness=1: this Gemini model returns one candidate per call,
            # and the default (3) asks for three at once and fails.
            ResponseRelevancy(strictness=1),
            LLMContextPrecisionWithReference(),
            LLMContextRecall(),
        ],
        llm=build_llm(),  # the app's Gemini is the judge
        embeddings=BgeEmbeddings(),
        # A few calls at a time, with patient retries if Gemini rate-limits us.
        run_config=RunConfig(max_workers=8, max_retries=10, timeout=180),
    )

    print(result)  # the four averages
    table = result.to_pandas()
    table.insert(0, "id", [r["id"] for r in rows])
    table.to_csv(SCORES, index=False)
    print(f"per-question scores saved to {SCORES.relative_to(ROOT)}")


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else ""
    if step == "answer":
        asyncio.run(answer())
    elif step == "score":
        # Optional number after "score": test on the first N answers only.
        score(int(sys.argv[2]) if len(sys.argv) > 2 else None)
    else:
        print("usage: ragas_eval.py answer | score [N]")
