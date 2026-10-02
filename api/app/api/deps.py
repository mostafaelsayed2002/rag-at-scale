"""FastAPI dependencies: hand routes the objects built at startup.

Routes declare them as types (e.g. `pipeline: Pipeline`), so tests can swap
them for fakes with app.dependency_overrides instead of patching globals.
"""

from pathlib import Path
from typing import Annotated

from fastapi import Depends, Request

from ..rag.pipeline import RagPipeline


def get_pipeline(request: Request) -> RagPipeline:
    return request.app.state.pipeline


def get_pdfs(request: Request) -> dict[str, Path]:
    return request.app.state.pdfs


Pipeline = Annotated[RagPipeline, Depends(get_pipeline)]
Pdfs = Annotated[dict[str, Path], Depends(get_pdfs)]
