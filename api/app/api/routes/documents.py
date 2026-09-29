from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from ...schemas.documents import Document, DocumentPage
from ...services import documents
from ..deps import Pdfs

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=DocumentPage)
async def list_documents(
    q: Annotated[str | None, Query(max_length=200, description="words in the title or CELEX id")] = None,
    collection: Annotated[str | None, Query(description="e.g. Regulation, Directive")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """One page of the acts, for the documents panel. Searched and paged here:
    the whole list is ~19 MB."""
    return await documents.list_documents(q, collection, limit, offset)


@router.get("/{doc_id}", response_model=Document)
async def get_document(doc_id: str, pdfs: Pdfs):
    row = await documents.get_document(doc_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No document {doc_id!r}")
    return {**row, "has_file": doc_id in pdfs}


@router.get("/{doc_id}/file")
async def get_document_file(doc_id: str, pdfs: Pdfs):
    """The original PDF, so the viewer can show the cited page itself.

    FileResponse answers range requests, which is what lets the viewer fetch
    one page instead of the whole file.
    """
    path = pdfs.get(doc_id)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail=f"No PDF for {doc_id!r}")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"{doc_id}.pdf",
        content_disposition_type="inline",
        # The corpus is static: let the browser keep it for a day.
        headers={"Cache-Control": "public, max-age=86400"},
    )
