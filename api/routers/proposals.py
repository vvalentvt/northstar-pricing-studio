"""Proposal HTTP endpoints -- generation, listing, detail, and PDF
download.

Thin translation + persistence-wiring boundary only: the actual
generation decision (version-concurrency guard, approval gate,
snapshot construction, rendering) lives entirely in
src/application/proposals.py. This router never calculates pricing,
never re-renders a PDF on download, and never exposes internal
pricing-governance fields or raw persistence errors to the client.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import ValidationError

from application import ProposalError, generate_proposal
from persistence import (
    ProposalNotFoundError,
    ProposalRepository,
    QuoteNotFoundError,
    QuoteRepository,
)
from proposals import ProposalNarrative, ProposalRenderer

from api.dependencies import (
    get_proposal_renderer,
    get_proposal_repository,
    get_quote_repository,
)
from api.dto_mapping import proposal_to_response_dto, proposal_to_summary_dto
from api.models import (
    CreateProposalRequestDto,
    ProposalResponseDto,
    ProposalSummaryDto,
)

router = APIRouter(tags=["proposals"])


@router.post(
    "/api/quotes/{quote_id}/proposals", response_model=ProposalResponseDto, status_code=201
)
def create_proposal(
    quote_id: str,
    request: CreateProposalRequestDto,
    quote_repository: QuoteRepository = Depends(get_quote_repository),
    proposal_repository: ProposalRepository = Depends(get_proposal_repository),
    renderer: ProposalRenderer = Depends(get_proposal_renderer),
) -> ProposalResponseDto:
    """Generate a durable Proposal from the Quote's currently committed
    version. 409 if the Quote has advanced past expectedVersionNumber
    or if the committed pricing requires approval; neither case
    persists anything."""
    try:
        narrative = ProposalNarrative(
            proposal_title=request.proposal_title,
            executive_summary=request.executive_summary,
            commercial_notes=request.commercial_notes,
            valid_through=request.valid_through,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        proposal = generate_proposal(
            quote_id,
            request.expected_version_number,
            narrative,
            quote_repository=quote_repository,
            proposal_repository=proposal_repository,
            renderer=renderer,
        )
    except QuoteNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ProposalError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return proposal_to_response_dto(proposal)


@router.get("/api/quotes/{quote_id}/proposals", response_model=list[ProposalSummaryDto])
def list_proposals_for_quote(
    quote_id: str,
    quote_repository: QuoteRepository = Depends(get_quote_repository),
    proposal_repository: ProposalRepository = Depends(get_proposal_repository),
) -> list[ProposalSummaryDto]:
    try:
        quote_repository.get(quote_id)
    except QuoteNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    proposals = proposal_repository.list_for_quote(quote_id)
    return [proposal_to_summary_dto(p) for p in proposals]


@router.get("/api/proposals/{proposal_id}", response_model=ProposalResponseDto)
def get_proposal(
    proposal_id: str,
    proposal_repository: ProposalRepository = Depends(get_proposal_repository),
) -> ProposalResponseDto:
    try:
        proposal = proposal_repository.get(proposal_id)
    except ProposalNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return proposal_to_response_dto(proposal)


@router.get("/api/proposals/{proposal_id}/pdf")
def download_proposal_pdf(
    proposal_id: str,
    proposal_repository: ProposalRepository = Depends(get_proposal_repository),
) -> Response:
    """Returns the exact persisted PDF bytes -- never regenerated."""
    try:
        proposal = proposal_repository.get(proposal_id)
        pdf_bytes = proposal_repository.get_pdf(proposal_id)
    except ProposalNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{proposal.filename}"'},
    )
