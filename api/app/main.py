from fastapi import FastAPI

app = FastAPI(title="RAG at Scale")


@app.get("/health")
async def health():
    return {"status": "ok"}
