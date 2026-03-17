"""Tender routes."""

import csv
from io import BytesIO, StringIO
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from models import (
    RiskScore,
    RiskCategory,
    TenderStatus,
    TenderWithRisk,
    TenderDetail,
)
from state import State
from intelligence.evidence import build_evidence_pack_async
from intelligence.agent import get_agent
from runtime_graph import ensure_runtime_graph

router = APIRouter(prefix="/api", tags=["tenders"])


def _collect_tender_results(
    state: State,
    *,
    risk_level: Optional[RiskCategory] = None,
    status: Optional[TenderStatus] = None,
    sort_by: str = "risk",
) -> list[TenderWithRisk]:
    results: list[TenderWithRisk] = []
    for tender_id, tender in state.tenders.items():
        risk = state.risk_scores.get(
            tender_id, RiskScore(overall=0, category=RiskCategory.LOW)
        )

        if risk_level and risk.category != risk_level:
            continue
        if status and tender.status != status:
            continue

        bidder_count = len(
            {b.company_id for b in state.bids_by_tender.get(tender_id, [])}
        )
        results.append(
            TenderWithRisk(tender=tender, risk=risk, bidder_count=bidder_count)
        )

    if sort_by == "risk":
        results.sort(key=lambda item: item.risk.overall, reverse=True)
    elif sort_by == "value":
        results.sort(
            key=lambda item: item.tender.estimated_value or 0,
            reverse=True,
        )
    elif sort_by == "date":
        results.sort(
            key=lambda item: (
                item.tender.published_date.isoformat()
                if item.tender.published_date
                else ""
            ),
            reverse=True,
        )

    return results


def _build_tender_report_pdf(detail: TenderDetail) -> bytes:
    tender = detail.tender
    risk = detail.risk
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
        title=f"Sentinel Risk Report - {tender.reference_number}",
    )
    styles = getSampleStyleSheet()
    title_color = colors.HexColor("#0f172a")
    accent_color = colors.HexColor("#1f4b46")
    accent_soft = colors.HexColor("#e8f3f1")
    border_color = colors.HexColor("#d7e3e1")
    muted_fill = colors.HexColor("#f7f8fa")
    risk_fill = {
        RiskCategory.HIGH: colors.HexColor("#fde9e5"),
        RiskCategory.MEDIUM: colors.HexColor("#f8f0df"),
        RiskCategory.LOW: colors.HexColor("#e7f4ee"),
    }
    risk_text = {
        RiskCategory.HIGH: colors.HexColor("#c4412f"),
        RiskCategory.MEDIUM: colors.HexColor("#b78b43"),
        RiskCategory.LOW: colors.HexColor("#1f6f5c"),
    }
    title_style = styles["Title"].clone("sentinel_title")
    title_style.textColor = title_color
    title_style.fontSize = 22
    title_style.leading = 27
    heading_style = styles["Heading2"].clone("sentinel_heading")
    heading_style.textColor = title_color
    heading_style.fontSize = 15
    heading_style.leading = 19
    section_style = styles["Heading3"].clone("sentinel_section")
    section_style.textColor = accent_color
    section_style.fontSize = 12
    section_style.leading = 15
    section_style.spaceAfter = 6
    factor_style = styles["Heading4"].clone("sentinel_factor")
    factor_style.textColor = title_color
    factor_style.fontSize = 10.5
    factor_style.leading = 13
    body_style = styles["BodyText"].clone("sentinel_body")
    body_style.textColor = colors.HexColor("#334155")
    body_style.fontSize = 9.5
    body_style.leading = 13
    meta_style = styles["Normal"].clone("sentinel_meta")
    meta_style.textColor = colors.HexColor("#64748b")
    meta_style.fontSize = 9
    meta_style.leading = 12
    compact_style = styles["BodyText"].clone("sentinel_compact")
    compact_style.textColor = colors.HexColor("#334155")
    compact_style.fontSize = 8.5
    compact_style.leading = 11
    compact_style.wordWrap = "CJK"
    header_compact_style = compact_style.clone("sentinel_compact_header")
    header_compact_style.textColor = colors.white
    header_compact_style.fontSize = 8
    story = [
        Paragraph("Sentinel Tender Risk Report", title_style),
        Spacer(1, 12),
        Paragraph(tender.title, heading_style),
        Paragraph(f"Reference: {tender.reference_number}", meta_style),
        Paragraph(f"Procuring Entity: {tender.procuring_entity}", meta_style),
        Spacer(1, 12),
    ]

    summary_rows = [
        ["Overall Risk Score", str(risk.overall)],
        ["Risk Category", risk.category.value],
        ["Tender Status", tender.status.value],
        [
            "Estimated Value",
            (
                f"KES {tender.estimated_value:,.0f}"
                if tender.estimated_value is not None
                else "Unknown"
            ),
        ],
        [
            "Awarded Amount",
            (
                f"KES {tender.awarded_amount:,.0f}"
                if tender.awarded_amount is not None
                else "Unknown"
            ),
        ],
        ["Bidder Count", str(len({b.company_id for b in detail.bids}))],
    ]
    summary_table = Table(summary_rows, colWidths=[170, 320])
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), accent_soft),
                ("BACKGROUND", (1, 0), (1, 1), risk_fill[risk.category]),
                ("TEXTCOLOR", (1, 0), (1, 1), risk_text[risk.category]),
                ("BOX", (0, 0), (-1, -1), 0.75, border_color),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, border_color),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, 1), "Helvetica-Bold"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend([summary_table, Spacer(1, 16)])

    if risk.recommendation:
        story.extend(
            [
                Paragraph("Recommended Actions", section_style),
                Paragraph(risk.recommendation.replace("\n", "<br/>"), body_style),
                Spacer(1, 12),
            ]
        )

    story.append(Paragraph("Risk Factors", section_style))
    if risk.factors:
        for index, factor in enumerate(risk.factors, start=1):
            evidence = (
                "<br/>".join(f"- {item}" for item in factor.evidence[:6])
                or "- No supporting evidence recorded"
            )
            story.extend(
                [
                    Paragraph(
                        f"{index}. {factor.type.value.replace('_', ' ')} ({factor.weight})",
                        factor_style,
                    ),
                    Paragraph(factor.description, body_style),
                    Paragraph(evidence, compact_style),
                    Spacer(1, 10),
                ]
            )
    else:
        story.extend(
            [Paragraph("No risk factors recorded.", body_style), Spacer(1, 10)]
        )

    if detail.bids:
        story.append(Paragraph("Bidder Participation", section_style))
        bid_rows = [
            [
                Paragraph("Company ID", header_compact_style),
                Paragraph("Price (KES)", header_compact_style),
                Paragraph("Submitted", header_compact_style),
                Paragraph("Technical Score", header_compact_style),
            ]
        ]
        for bid in detail.bids:
            bid_rows.append(
                [
                    Paragraph(str(bid.company_id), compact_style),
                    Paragraph(
                        (
                            f"{bid.amount:,.0f}"
                            if bid.amount is not None
                            else "Not disclosed"
                        ),
                        compact_style,
                    ),
                    Paragraph(
                        (
                            bid.submission_date.isoformat()
                            if hasattr(bid.submission_date, "isoformat")
                            else str(bid.submission_date)
                        ),
                        compact_style,
                    ),
                    Paragraph(
                        "" if bid.technical_score is None else str(bid.technical_score),
                        compact_style,
                    ),
                ]
            )
        bid_table = Table(bid_rows, colWidths=[220, 95, 120, 55], repeatRows=1)
        bid_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), accent_color),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, muted_fill]),
                    ("BOX", (0, 0), (-1, -1), 0.75, border_color),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, border_color),
                    ("PADDING", (0, 0), (-1, -1), 5),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                    ("ALIGN", (3, 1), (3, -1), "CENTER"),
                ]
            )
        )
        story.append(bid_table)

    doc.build(story)
    return buffer.getvalue()


@router.get("/tenders", response_model=list[TenderWithRisk])
def get_tenders(
    state: State,
    risk_level: Optional[RiskCategory] = Query(
        None, description="Filter by risk level"
    ),
    status: Optional[TenderStatus] = Query(None, description="Filter by tender status"),
    sort_by: str = Query("risk", description="Sort by: risk, value, date"),
    limit: int = Query(50, ge=1, le=100),
):
    """Get list of tenders with risk scores."""
    results = _collect_tender_results(
        state, risk_level=risk_level, status=status, sort_by=sort_by
    )
    return results[:limit]


@router.get("/tenders/export.csv")
def export_tenders_csv(
    state: State,
    risk_level: Optional[RiskCategory] = Query(None),
    status: Optional[TenderStatus] = Query(None),
    sort_by: str = Query("risk", description="Sort by: risk, value, date"),
):
    """Export filtered tenders and risk summary as CSV."""
    results = _collect_tender_results(
        state, risk_level=risk_level, status=status, sort_by=sort_by
    )
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "tender_id",
            "reference_number",
            "title",
            "procuring_entity",
            "status",
            "risk_score",
            "risk_category",
            "bidder_count",
            "estimated_value",
            "awarded_amount",
            "published_date",
            "deadline",
            "procurement_method",
            "source_system",
        ]
    )
    for item in results:
        tender = item.tender
        writer.writerow(
            [
                tender.id,
                tender.reference_number,
                tender.title,
                tender.procuring_entity,
                tender.status.value,
                item.risk.overall,
                item.risk.category.value,
                item.bidder_count,
                tender.estimated_value or "",
                tender.awarded_amount or "",
                tender.published_date.isoformat() if tender.published_date else "",
                tender.deadline.isoformat() if tender.deadline else "",
                tender.procurement_method or "",
                tender.source_system or "",
            ]
        )

    filename = "sentinel-tenders.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/tenders/{tender_id}", response_model=TenderDetail)
def get_tender_detail(tender_id: str, state: State):
    """Get detailed tender information with full risk breakdown."""
    if tender_id not in state.tenders:
        raise HTTPException(status_code=404, detail="Tender not found")

    tender = state.tenders[tender_id]
    risk = state.risk_scores.get(
        tender_id, RiskScore(overall=0, category=RiskCategory.LOW)
    )
    tender_bids = state.bids_by_tender.get(tender_id, [])

    winning_company = None
    if tender.awarded_to and tender.awarded_to in state.companies:
        winning_company = state.companies[tender.awarded_to]

    return TenderDetail(
        tender=tender, risk=risk, bids=tender_bids, winning_company=winning_company
    )


@router.get("/tenders/{tender_id}/report.pdf")
def export_tender_risk_report(tender_id: str, state: State):
    """Export a tender risk report as PDF."""
    if tender_id not in state.tenders:
        raise HTTPException(status_code=404, detail="Tender not found")

    detail = get_tender_detail(tender_id, state)
    pdf_bytes = _build_tender_report_pdf(detail)
    filename = f"tender-risk-report-{tender_id}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/tenders/{tender_id}/evidence")
async def get_evidence_pack(tender_id: str, state: State):
    """Get structured evidence pack for a tender."""
    if tender_id not in state.tenders:
        raise HTTPException(status_code=404, detail="Tender not found")

    tender = state.tenders[tender_id]
    risk = state.risk_scores.get(
        tender_id, RiskScore(overall=0, category=RiskCategory.LOW)
    )
    tender_bids = state.bids_by_tender.get(tender_id, [])

    graph = ensure_runtime_graph(state)
    pack = await build_evidence_pack_async(
        tender, risk, tender_bids, state.companies, graph
    )
    return pack.to_dict()


@router.get("/tenders/{tender_id}/explain")
async def explain_tender_risk(tender_id: str, state: State):
    """Get AI-generated explanation for a tender's risk score."""
    if tender_id not in state.tenders:
        raise HTTPException(status_code=404, detail="Tender not found")

    tender = state.tenders[tender_id]
    risk = state.risk_scores.get(
        tender_id, RiskScore(overall=0, category=RiskCategory.LOW)
    )
    tender_bids = state.bids_by_tender.get(tender_id, [])

    # Use async variant so Neo4j paths are resolved before LLM prompt is built
    graph = ensure_runtime_graph(state)
    pack = await build_evidence_pack_async(
        tender, risk, tender_bids, state.companies, graph
    )
    agent = get_agent()
    result = await agent.explain(pack)
    return result
