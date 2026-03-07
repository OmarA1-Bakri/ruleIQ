"""

PDF generation service using ReportLab for ComplianceGPT
"""

import base64
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


class PDFGenerator:
    """Generate PDF reports from structured data"""

    def __init__(self) -> None:
        self.colors = self._setup_colors()
        self.styles = self._setup_styles()

    def _setup_colors(self):
        """Setup custom color scheme for ComplianceGPT branding"""
        return {
            "primary": colors.HexColor("#1a5490"),  # Deep blue
            "secondary": colors.HexColor("#2c5aa0"),  # Medium blue
            "accent": colors.HexColor("#27ae60"),  # Green
            "warning": colors.HexColor("#f39c12"),  # Orange
            "danger": colors.HexColor("#e74c3c"),  # Red
            "light_gray": colors.HexColor("#ecf0f1"),  # Light gray
            "medium_gray": colors.HexColor("#7f8c8d"),  # Medium gray
            "dark_gray": colors.HexColor("#2c3e50"),  # Dark gray,
        }

    def _setup_styles(self):
        """Setup custom styles for the PDF document."""
        styles = getSampleStyleSheet()

        # Title styles
        styles.add(
            ParagraphStyle(
                name="ReportTitle",
                parent=styles["Title"],
                fontSize=28,
                textColor=self.colors["primary"],
                spaceAfter=20,
                alignment=TA_CENTER,
                fontName="Helvetica-Bold",
            ),
        )

        styles.add(
            ParagraphStyle(
                name="ReportSubtitle",
                parent=styles["Normal"],
                fontSize=14,
                textColor=self.colors["medium_gray"],
                spaceAfter=30,
                alignment=TA_CENTER,
                fontName="Helvetica",
            ),
        )

        # Section headers
        styles.add(
            ParagraphStyle(
                name="SectionHeader",
                parent=styles["Heading1"],
                fontSize=18,
                textColor=self.colors["secondary"],
                spaceAfter=12,
                spaceBefore=20,
                fontName="Helvetica-Bold",
                borderWidth=1,
                borderColor=self.colors["primary"],
                borderPadding=4,
                backColor=self.colors["light_gray"],
            ),
        )

        styles.add(
            ParagraphStyle(
                name="SubsectionHeader",
                parent=styles["Heading2"],
                fontSize=14,
                textColor=self.colors["dark_gray"],
                spaceAfter=8,
                spaceBefore=12,
                fontName="Helvetica-Bold",
            ),
        )

        # Metrics and values
        styles.add(
            ParagraphStyle(
                name="MetricValue",
                parent=styles["Normal"],
                fontSize=32,
                textColor=self.colors["accent"],
                alignment=TA_CENTER,
                fontName="Helvetica-Bold",
                spaceAfter=4,
            ),
        )

        styles.add(
            ParagraphStyle(
                name="MetricLabel",
                parent=styles["Normal"],
                fontSize=11,
                textColor=self.colors["medium_gray"],
                alignment=TA_CENTER,
                fontName="Helvetica",
                spaceAfter=16,
            ),
        )

        # Status indicators
        styles.add(
            ParagraphStyle(
                name="StatusExcellent",
                parent=styles["Normal"],
                fontSize=12,
                textColor=self.colors["accent"],
                fontName="Helvetica-Bold",
                alignment=TA_CENTER,
            ),
        )

        styles.add(
            ParagraphStyle(
                name="StatusGood",
                parent=styles["Normal"],
                fontSize=12,
                textColor=colors.HexColor("#27ae60"),
                fontName="Helvetica-Bold",
                alignment=TA_CENTER,
            ),
        )

        styles.add(
            ParagraphStyle(
                name="StatusWarning",
                parent=styles["Normal"],
                fontSize=12,
                textColor=self.colors["warning"],
                fontName="Helvetica-Bold",
                alignment=TA_CENTER,
            ),
        )

        styles.add(
            ParagraphStyle(
                name="StatusCritical",
                parent=styles["Normal"],
                fontSize=12,
                textColor=self.colors["danger"],
                fontName="Helvetica-Bold",
                alignment=TA_CENTER,
            ),
        )

        # Content styles
        styles.add(
            ParagraphStyle(
                name="ReportBodyText",
                parent=styles["Normal"],
                fontSize=11,
                textColor=self.colors["dark_gray"],
                alignment=TA_JUSTIFY,
                spaceAfter=8,
                leading=14,
            ),
        )

        styles.add(
            ParagraphStyle(
                name="ReportBulletPoint",
                parent=styles["Normal"],
                fontSize=11,
                textColor=self.colors["dark_gray"],
                leftIndent=20,
                bulletIndent=10,
                spaceAfter=6,
                leading=13,
            ),
        )

        return styles

    async def generate_pdf(self, report_data: Dict[str, Any], output_format: str = "bytes") -> Any:
        """Generate PDF from report data."""
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            topMargin=1 * inch,
            bottomMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            rightMargin=0.75 * inch,
        )

        story = []
        report_type = report_data.get("report_type", "unknown")

        # Build document header
        story.extend(self._build_header(report_data))

        # Build body based on report type
        if report_type == "executive_summary":
            story.extend(self._build_executive_summary(report_data))
        elif report_type == "gap_analysis":
            story.extend(self._build_gap_analysis(report_data))
        elif report_type == "evidence_report":
            story.extend(self._build_evidence_report(report_data))
        elif report_type == "audit_readiness":
            story.extend(self._build_audit_readiness(report_data))
        elif report_type == "compliance_status":
            story.extend(self._build_compliance_status(report_data))
        else:
            story.append(
                Paragraph(
                    f"Report type '{report_type}' is not yet implemented.",
                    self.styles["ReportBodyText"],
                ),
            )

        # Build document
        doc.build(
            story,
            onFirstPage=self._add_page_template,
            onLaterPages=self._add_page_template,
        )

        buffer.seek(0)
        if output_format == "bytes":
            return buffer.getvalue()
        elif output_format == "base64":
            return base64.b64encode(buffer.getvalue()).decode()
        return buffer

    def _build_header(self, report_data: Dict) -> List:
        """Build the report header section."""
        title_text = (
            report_data.get("report_type", "compliance_report").replace("_", " ").title(),
        )
        company_name = report_data.get("business_profile", {}).get(
            "name",
            "Unknown Company",
        )
        generated_date = datetime.fromisoformat(report_data["generated_at"]).strftime(
            "%B %d, %Y at %I:%M %p",
        )

        return [
            Paragraph(f"ComplianceGPT {title_text}", self.styles["ReportTitle"]),
            Paragraph(f"Prepared for: {company_name}", self.styles["ReportSubtitle"]),
            Paragraph(f"Generated on: {generated_date}", self.styles["ReportSubtitle"]),
            Spacer(1, 0.3 * inch),
        ]

    def _build_executive_summary(self, report_data: Dict) -> List:
        """Build the executive summary section."""
        story = []

        # Overview section
        story.append(Paragraph("Executive Overview", self.styles["SectionHeader"]))

        business_profile = report_data.get("business_profile", {})
        overview_text = f"""
        This executive summary provides a high-level overview of compliance status for {
            business_profile.get("name", "your organization")
        },
        a {business_profile.get("industry", "technology")} company with {
            business_profile.get("employee_count", "unknown")
        } employees
        based in {business_profile.get("country", "the UK")}.
        """
        story.append(Paragraph(overview_text, self.styles["ReportBodyText"]))
        story.append(Spacer(1, 0.2 * inch))

        # Key metrics section
        story.append(
            Paragraph("Key Performance Indicators", self.styles["SectionHeader"]),
        )

        key_metrics = report_data.get("key_metrics", {})
        if key_metrics:
            # Create simple metrics display
            for key, value in key_metrics.items():
                label = key.replace("_", " ").title()

                if isinstance(value, float):
                    value_str = f"{value:.1f}%" if "percentage" in key.lower() else f"{value:.1f}"
                else:
                    value_str = str(value)

                story.append(Paragraph(value_str, self.styles["MetricValue"]))
                story.append(Paragraph(label, self.styles["MetricLabel"]))
                story.append(Spacer(1, 0.1 * inch))

        story.append(Spacer(1, 0.3 * inch))

        # Framework summary
        summary = report_data.get("summary", {})
        if summary:
            story.append(
                Paragraph("Compliance Framework Status", self.styles["SectionHeader"]),
            )

            framework_data = [["Framework", "Score", "Status", "Gaps", "Evidence %"]]
            for framework, data in summary.items():
                status_style = self._get_status_style(data.get("status", "Unknown"))
                framework_data.append(
                    [
                        framework.upper(),
                        f"{data.get('overall_score', 0):.1f}%",
                        Paragraph(data.get("status", "Unknown"), status_style),
                        str(data.get("gaps_count", 0)),
                        f"{data.get('evidence_completion', 0):.1f}%",
                    ],
                )

            framework_table = Table(
                framework_data,
                colWidths=[1.3 * inch, 1 * inch, 1.2 * inch, 0.8 * inch, 1 * inch],
            )
            framework_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), self.colors["primary"]),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 11),
                        ("FONTSIZE", (0, 1), (-1, -1), 10),
                        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.black),
                        ("BOX", (0, 0), (-1, -1), 0.5, self.colors["primary"]),
                        (
                            "ROWBACKGROUNDS",
                            (0, 1),
                            (-1, -1),
                            [colors.white, self.colors["light_gray"]],
                        ),
                    ],
                ),
            )
            story.append(framework_table)

        story.append(Spacer(1, 0.3 * inch))

        # Recommendations
        recommendations = report_data.get("recommendations", [])
        if recommendations:
            story.append(
                Paragraph("Priority Recommendations", self.styles["SectionHeader"]),
            )

            for i, rec in enumerate(recommendations[:5], 1):
                rec_title = f"{i}. {rec.get('title', 'Recommendation')}"
                story.append(Paragraph(rec_title, self.styles["SubsectionHeader"]))

                rec_text = f"""
                <b>Description:</b> {rec.get("description", "No description available")}<br/>
                <b>Impact:</b> {rec.get("impact", "Unknown")} |
                <b>Effort:</b> {rec.get("effort", "Unknown")} |
                <b>Framework:</b> {rec.get("framework", "General")}
                """
                story.append(Paragraph(rec_text, self.styles["ReportBodyText"]))
                story.append(Spacer(1, 0.1 * inch))

        return story

    def _build_gap_analysis(self, report_data: Dict) -> List:
        """Build the gap analysis section."""
        story = []

        story.append(Paragraph("Compliance Gap Analysis", self.styles["SectionHeader"]))

        # Summary statistics
        summary = report_data.get("summary", {})
        summary_text = f"""
        This analysis identified <b>{summary.get("total_gaps", 0)} total compliance gaps</b> across your
        compliance frameworks, including {summary.get("critical_gaps", 0)} critical gaps,
        {summary.get("high_gaps", 0)} high-priority gaps, and {summary.get("medium_gaps", 0)} medium-priority gaps.
        """
        story.append(Paragraph(summary_text, self.styles["ReportBodyText"]))
        story.append(Spacer(1, 0.2 * inch))

        # Gap details by framework
        gaps = report_data.get("gaps", {})
        if gaps:
            story.append(
                Paragraph(
                    "Identified Gaps by Framework",
                    self.styles["SubsectionHeader"],
                ),
            )

            gap_data = [
                ["Framework", "Category", "Gap Description", "Severity", "Effort"],
            ]

            for framework, categories in gaps.items():
                for category, gap_list in categories.items():
                    for gap in gap_list:
                        severity_color = self._get_severity_color(
                            gap.get("severity", "medium"),
                        )
                        gap_data.append(
                            [
                                framework.upper(),
                                category,
                                Paragraph(
                                    gap.get("title", "Unknown Gap"),
                                    self.styles["ReportBodyText"],
                                ),
                                Paragraph(
                                    gap.get("severity", "Medium").title(),
                                    ParagraphStyle(
                                        "temp",
                                        textColor=severity_color,
                                        fontSize=10,
                                        fontName="Helvetica-Bold",
                                    ),
                                ),
                                gap.get("remediation_effort", "Unknown"),
                            ],
                        )

            if len(gap_data) > 1:
                gap_table = Table(
                    gap_data,
                    colWidths=[1 * inch, 1 * inch, 2.8 * inch, 0.8 * inch, 0.8 * inch],
                )
                gap_table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), self.colors["secondary"]),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                            (
                                "ALIGN",
                                (3, 0),
                                (-1, -1),
                                "CENTER",
                            ),  # Center severity and effort columns
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, 0), 10),
                            ("FONTSIZE", (0, 1), (-1, -1), 9),
                            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.black),
                            ("BOX", (0, 0), (-1, -1), 0.5, self.colors["secondary"]),
                            (
                                "ROWBACKGROUNDS",
                                (0, 1),
                                (-1, -1),
                                [colors.white, self.colors["light_gray"]],
                            ),
                        ],
                    ),
                )
                story.append(gap_table)

        story.append(Spacer(1, 0.3 * inch))

        # Remediation plan
        remediation_plan = report_data.get("remediation_plan", [])
        if remediation_plan:
            story.append(
                Paragraph(
                    "Recommended Remediation Plan",
                    self.styles["SubsectionHeader"],
                ),
            )

            current_phase = None
            for item in remediation_plan:
                phase = item.get("phase", "Unknown Phase")
                if phase != current_phase:
                    current_phase = phase
                    story.append(Paragraph(phase, self.styles["SubsectionHeader"]))

                item_text = f"""
                <b>{item.get("title", "Remediation Item")}</b><br/>
                {item.get("description", "No description available")}<br/>
                <i>Effort: {item.get("effort", "Unknown")} | Impact: {item.get("impact", "Unknown")}</i>
                """
                story.append(Paragraph(item_text, self.styles["ReportBulletPoint"]))
                story.append(Spacer(1, 0.05 * inch))

        return story

    def _build_evidence_report(self, report_data: Dict) -> List:
        """Build the evidence collection report section."""
        story = []

        story.append(
            Paragraph("Evidence Collection Report", self.styles["SectionHeader"]),
        )

        # Summary by framework
        evidence_summary = report_data.get("evidence_summary", {})
        if evidence_summary:
            story.append(
                Paragraph(
                    "Evidence Collection Status by Framework",
                    self.styles["SubsectionHeader"],
                ),
            )

            evidence_data = [
                ["Framework", "Total Items", "Completion %", "Automation Opportunities"],
            ]
            for framework, data in evidence_summary.items():
                evidence_data.append(
                    [
                        framework.upper(),
                        str(data.get("total_items", 0)),
                        f"{data.get('completion_percentage', 0):.1f}%",
                        str(data.get("automation_opportunities", 0)),
                    ],
                )

            evidence_table = Table(
                evidence_data,
                colWidths=[1.5 * inch, 1 * inch, 1.2 * inch, 1.8 * inch],
            )
            evidence_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), self.colors["primary"]),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 11),
                        ("FONTSIZE", (0, 1), (-1, -1), 10),
                        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.black),
                        ("BOX", (0, 0), (-1, -1), 0.5, self.colors["primary"]),
                        (
                            "ROWBACKGROUNDS",
                            (0, 1),
                            (-1, -1),
                            [colors.white, self.colors["light_gray"]],
                        ),
                    ],
                ),
            )
            story.append(evidence_table)

        story.append(Spacer(1, 0.2 * inch))

        # Automation opportunities
        automation_opportunities = report_data.get("automation_opportunities", [])
        if automation_opportunities:
            story.append(
                Paragraph(
                    "Priority Automation Opportunities",
                    self.styles["SubsectionHeader"],
                ),
            )

            for opp in automation_opportunities[:10]:  # Show top 10
                opp_text = f"""
                <b>{opp.get("evidence_name", "Unknown Evidence")}</b> ({opp.get("framework", "Unknown").upper()})<br/>
                Automation Source: {opp.get("automation_source", "Unknown")}<br/>
                Priority: {opp.get("priority", "Unknown")}
                """
                story.append(Paragraph(opp_text, self.styles["ReportBulletPoint"]))
                story.append(Spacer(1, 0.05 * inch))

        return story

    def _build_audit_readiness(self, report_data: Dict) -> List:
        """Build the audit readiness report section."""
        story = []

        story.append(
            Paragraph("Audit Readiness Assessment", self.styles["SectionHeader"]),
        )

        # Readiness scores
        readiness_scores = report_data.get("readiness_scores", {})
        if readiness_scores:
            story.append(
                Paragraph("Framework Readiness Scores", self.styles["SubsectionHeader"]),
            )

            readiness_data = [
                [
                    "Framework",
                    "Overall Score",
                    "Evidence %",
                    "Policy %",
                    "Gaps Remaining",
                ],
            ]
            for framework, scores in readiness_scores.items():
                readiness_data.append(
                    [
                        framework.upper(),
                        f"{scores.get('overall_score', 0):.1f}%",
                        f"{scores.get('evidence_completion', 0):.1f}%",
                        f"{scores.get('policy_completion', 0):.1f}%",
                        str(scores.get("gaps_remaining", 0)),
                    ],
                )

            readiness_table = Table(
                readiness_data,
                colWidths=[1.2 * inch, 1 * inch, 1 * inch, 1 * inch, 1 * inch],
            )
            readiness_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), self.colors["primary"]),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 11),
                        ("FONTSIZE", (0, 1), (-1, -1), 10),
                        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.black),
                        ("BOX", (0, 0), (-1, -1), 0.5, self.colors["primary"]),
                        (
                            "ROWBACKGROUNDS",
                            (0, 1),
                            (-1, -1),
                            [colors.white, self.colors["light_gray"]],
                        ),
                    ],
                ),
            )
            story.append(readiness_table)

        story.append(Spacer(1, 0.2 * inch))

        # Critical items requiring attention
        critical_items = report_data.get("critical_items", [])
        if critical_items:
            story.append(
                Paragraph(
                    "Critical Items Requiring Immediate Attention",
                    self.styles["SubsectionHeader"],
                ),
            )

            for item in critical_items[:8]:  # Show top 8 critical items
                self._get_severity_color(item.get("severity", "medium"))
                item_text = f"""
                <b>{item.get("title", "Critical Item")}</b> ({item.get("framework", "Unknown").upper()})<br/>
                {item.get("description", "No description available")}<br/>
                <i>Severity: {item.get("severity", "Unknown")} | Effort: {item.get("remediation_effort", "Unknown")}</i>
                """
                story.append(Paragraph(item_text, self.styles["ReportBulletPoint"]))
                story.append(Spacer(1, 0.05 * inch))

        return story

    def _build_compliance_status(self, report_data: Dict) -> List:
        """Build the compliance status report section."""
        story = []

        story.append(
            Paragraph("Compliance Status Overview", self.styles["SectionHeader"]),
        )

        # Overall metrics
        overall_metrics = report_data.get("overall_metrics", {})
        if overall_metrics:
            metrics_text = f"""
            Average Compliance Score: <b>{overall_metrics.get("average_score", 0):.1f}%</b><br/>
            Frameworks Assessed: <b>{overall_metrics.get("frameworks_assessed", 0)}</b><br/>
            Overall Status: <b>{overall_metrics.get("overall_status", "Unknown")}</b>
            """
            story.append(Paragraph(metrics_text, self.styles["ReportBodyText"]))
            story.append(Spacer(1, 0.2 * inch))

        # Framework status details
        framework_status = report_data.get("framework_status", {})
        if framework_status:
            story.append(
                Paragraph("Framework-Specific Status", self.styles["SubsectionHeader"]),
            )

            status_data = [["Framework", "Score", "Status", "Last Assessed", "Gaps"]]
            for framework, status in framework_status.items():
                status_style = self._get_status_style(status.get("status", "Unknown"))
                status_data.append(
                    [
                        framework.upper(),
                        f"{status.get('score', 0):.1f}%",
                        Paragraph(status.get("status", "Unknown"), status_style),
                        status.get("last_assessed", "Never"),
                        str(status.get("gaps", 0)),
                    ],
                )

            status_table = Table(
                status_data,
                colWidths=[1.3 * inch, 1 * inch, 1.2 * inch, 1.2 * inch, 0.8 * inch],
            )
            status_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), self.colors["primary"]),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 11),
                        ("FONTSIZE", (0, 1), (-1, -1), 10),
                        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.black),
                        ("BOX", (0, 0), (-1, -1), 0.5, self.colors["primary"]),
                        (
                            "ROWBACKGROUNDS",
                            (0, 1),
                            (-1, -1),
                            [colors.white, self.colors["light_gray"]],
                        ),
                    ],
                ),
            )
            story.append(status_table)

        return story

    def _get_status_style(self, status: str) -> ParagraphStyle:
        """Get the appropriate style for a status value."""
        status_lower = status.lower()
        if status_lower in ["excellent", "good"]:
            return self.styles["StatusExcellent"]
        elif status_lower in ["satisfactory"]:
            return self.styles["StatusGood"]
        elif status_lower in ["needs improvement"]:
            return self.styles["StatusWarning"]
        else:
            return self.styles["StatusCritical"]

    def _get_severity_color(self, severity: str) -> colors.Color:
        """Get color for severity level."""
        severity_lower = severity.lower()
        if severity_lower == "critical":
            return self.colors["danger"]
        elif severity_lower == "high":
            return self.colors["warning"]
        elif severity_lower == "medium":
            return self.colors["medium_gray"]
        else:
            return self.colors["accent"]

    def _add_page_template(self, canvas, doc) -> None:
        """Add header and footer to each page."""
        canvas.saveState()

        # Header
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(self.colors["medium_gray"])
        canvas.drawString(
            doc.leftMargin,
            doc.height + doc.topMargin - 30,
            "ComplianceGPT Report",
        )

        # Footer
        canvas.setFont("Helvetica", 8)
        page_num_text = f"Page {doc.page}"
        canvas.drawRightString(
            doc.width + doc.leftMargin,
            doc.bottomMargin - 20,
            page_num_text,
        )

        # Footer line
        canvas.setStrokeColor(self.colors["light_gray"])
        canvas.setLineWidth(0.5)
        canvas.line(
            doc.leftMargin,
            doc.bottomMargin - 10,
            doc.width + doc.leftMargin,
            doc.bottomMargin - 10,
        )

        canvas.restoreState()
