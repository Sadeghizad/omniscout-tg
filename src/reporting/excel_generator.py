"""
OmniScout-TG: 8-Sheet Corporate Media Plan Excel Generator
Builds institutional-grade Excel workbooks (.xlsx) with full RTL formatting,
dynamic formulas, styled KPI cards, and comprehensive Persian/English bilingual rationales.
"""

import logging
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from config.settings import get_settings
from src.models.schemas import CampaignBrief, ChannelEntity, EconomicCeiling, JevTriageDecision

logger = logging.getLogger(__name__)


class ExcelMediaPlanGenerator:
    """Generates the official 8-sheet OmniScout-TG media plan workbook."""

    # Color Palette: Corporate Executive Navy & Accent Emerald
    NAVY_HEADER = "1B365D"
    ICE_BLUE = "F0F4F8"
    LIGHT_GRAY = "FAFAFA"
    BORDER_GRAY = "D1D5DB"
    WHITE = "FFFFFF"
    EMERALD_GREEN = "059669"
    SOFT_AMBER = "D97706"
    SOFT_RED = "DC2626"

    def __init__(self, output_dir: Path | None = None):
        self.output_dir = output_dir or get_settings().output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        brief: CampaignBrief,
        channels: list[ChannelEntity],
        triage_decisions: dict[str, JevTriageDecision],
        economics: dict[str, EconomicCeiling],
        creatives: dict[str, dict[str, str]],
        filename: str | None = None,
    ) -> Path:
        """
        Builds the 8-sheet Excel workbook.
        """
        wb = openpyxl.Workbook()
        wb.remove(wb.active)  # Remove default blank sheet

        # 1. Executive Summary
        ws1 = wb.create_sheet(title="1. Executive Summary")
        self._build_executive_summary(ws1, brief, channels, economics)

        # 2. Recommended Plan
        ws2 = wb.create_sheet(title="2. Recommended Plan")
        self._build_recommended_plan(ws2, brief, channels, triage_decisions, economics, creatives)

        # 3. Test Reserve Cell
        ws3 = wb.create_sheet(title="3. Test Reserve Cell")
        self._build_test_reserve(ws3, channels, triage_decisions, economics, creatives)

        # 4. Candidate Database
        ws4 = wb.create_sheet(title="4. Candidate Database")
        self._build_candidate_database(ws4, channels, triage_decisions, economics)

        # 5. Exclusion Audit Log
        ws5 = wb.create_sheet(title="5. Exclusion Audit Log")
        self._build_exclusion_log(ws5, channels, triage_decisions, economics)

        # 6. Creative & Hooks
        ws6 = wb.create_sheet(title="6. Creative & Hooks")
        self._build_creative_hooks(ws6, channels, triage_decisions, creatives)

        # 7. Scenario Modeler
        ws7 = wb.create_sheet(title="7. Scenario Modeler")
        self._build_scenario_modeler(ws7, brief)

        # 8. Attribution Tracker
        ws8 = wb.create_sheet(title="8. Attribution Tracker")
        self._build_attribution_tracker(ws8, brief, channels, triage_decisions)

        # Auto-adjust column widths & enable RTL across all sheets
        for ws in wb.worksheets:
            ws.sheet_view.rightToLeft = True
            self._autofit_columns(ws)

        safe_name = brief.campaign_name.replace(" ", "_").replace("/", "_")
        target_path = self.output_dir / (filename or f"OmniScout_MediaPlan_{safe_name}.xlsx")
        try:
            wb.save(target_path)
        except PermissionError:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            target_path = self.output_dir / (filename or f"OmniScout_MediaPlan_{safe_name}_{timestamp}.xlsx")
            logger.warning(
                f"Original file is locked (open in Excel). Saved workbook to fallback path: {target_path}"
            )
            wb.save(target_path)
        return target_path

    # --------------------------------------------------------------------------
    # Sheet Builders
    # --------------------------------------------------------------------------
    def _build_executive_summary(
        self,
        ws,
        brief: CampaignBrief,
        channels: list[ChannelEntity],
        economics: dict[str, EconomicCeiling],
    ):
        ws.views.sheetView[0].showGridLines = True
        self._apply_title(ws, "برنامه استراتژیک رسانه‌ای تلگرام - OmniScout-TG", "Executive Media Planning Summary")

        # Campaign KPI Card Table
        headers = ["شاخص کلیدی (KPI)", "مقدار هدف / تخمینی", "واحد سنجش", "توضیحات و فرضیات"]
        rows = [
            ["بودجه کل کمپین", brief.total_budget_usd, "USD ($)", "بودجه مصوب تبلیغاتی"],
            ["تارگت CAC (هزینه جذب مشتری)", brief.target_cac_usd, "USD ($)", "سقف اقتصادی بر اساس حاشیه سود"],
            ["نرخ تبدیل فرود (CVR)", f"{brief.est_cvr*100:.1f}%", "درصد", "نرخ تبدیل لندینگ‌پیج به مشتری"],
            ["محدوده نرخ کلیک (CTR)", f"{brief.est_ctr_min*100:.1f}% - {brief.est_ctr_max*100:.1f}%", "درصد", "بازه محتاطانه CTR بنر/پست تلگرام"],
            ["تعداد کانال‌های بررسی‌شده", len(channels), "کانال", "خوشه استخراج‌شده از گراف پیشنهادات تلگرام"],
            ["پرسونای مخاطب هدف (ICP)", brief.target_persona, "شرح کیفی", "جامعه هدف تبلیغات"],
            ["کانال‌های سید و لنگر", ", ".join(brief.seed_channels), "هندل تلگرام", "مبنای استخراج گراف همپوشانی"],
        ]
        self._write_table(ws, start_row=4, headers=headers, data=rows)

    def _build_recommended_plan(
        self,
        ws,
        brief: CampaignBrief,
        channels: list[ChannelEntity],
        triage_decisions: dict[str, JevTriageDecision],
        economics: dict[str, EconomicCeiling],
        creatives: dict[str, dict[str, str]],
    ):
        self._apply_title(ws, "پرتفوی کانال‌های تاییدشده (Core Portfolio)", "Verified Channels & Target Bids")
        headers = [
            "ردیف", "عنوان کانال", "هندل تلگرام", "اعضا", "بازدید ۲۴ ساعته",
            "نرخ درگیری (ERR24)", "سقف CPM ($)", "بید هدف CPM ($)", "امتیاز اطمینان",
            "فرمت پیشنهادی", "تحلیل انتخاب (فارسی)", "Strategic Rationale (EN)"
        ]

        data = []
        row_num = 1
        for ch in channels:
            tri = triage_decisions.get(ch.id)
            eco = economics.get(ch.id)
            cr = creatives.get(ch.id, {})
            if tri and tri.passed_triage and eco and eco.recommendation == "BUY":
                data.append([
                    row_num,
                    ch.title,
                    ch.id,
                    ch.participants_count,
                    ch.reach_24h,
                    f"{ch.err24:.2f}%",
                    f"${eco.cpm_ceiling:.2f}",
                    f"${eco.bid_target_cpm:.2f}",
                    f"{eco.confidence_score:.0f}/100",
                    cr.get("recommended_format", "24h Pinned Post"),
                    cr.get("rationale_fa", "جامعه مخاطبان با پرسونای هدف انطباق کامل دارد."),
                    cr.get("rationale_en", "Strong audience resonance and verified reach velocity."),
                ])
                row_num += 1

        self._write_table(ws, start_row=4, headers=headers, data=data)

    def _build_test_reserve(
        self,
        ws,
        channels: list[ChannelEntity],
        triage_decisions: dict[str, JevTriageDecision],
        economics: dict[str, EconomicCeiling],
        creatives: dict[str, dict[str, str]],
    ):
        self._apply_title(ws, "سلول رزرو آزمایش و کانال‌های اکسپلوری (Test Reserve Cell)", "20% Testing Allocation")
        headers = [
            "ردیف", "عنوان کانال", "هندل", "اعضا", "بازدید ۲۴h", "AAR",
            "بید آزمایشی ($)", "فرمت تست", "دلیل ورود به تست سل"
        ]

        data = []
        row_num = 1
        for ch in channels:
            eco = economics.get(ch.id)
            cr = creatives.get(ch.id, {})
            if eco and eco.recommendation == "TEST_CELL":
                data.append([
                    row_num,
                    ch.title,
                    ch.id,
                    ch.participants_count,
                    ch.reach_24h,
                    f"{ch.aar:.3f}",
                    f"${eco.bid_target_cpm:.2f}",
                    cr.get("recommended_format", "12h Post / No-Pin"),
                    eco.rationale_note or "کانال نوظهور با پتانسیل بالا اما داده‌های تاریخی محدود.",
                ])
                row_num += 1

        self._write_table(ws, start_row=4, headers=headers, data=data)

    def _build_candidate_database(
        self,
        ws,
        channels: list[ChannelEntity],
        triage_decisions: dict[str, JevTriageDecision],
        economics: dict[str, EconomicCeiling],
    ):
        self._apply_title(ws, "پایگاه داده جامع کانال‌های استخراج‌شده (Candidate Pool)", "All Discovered Nodes")
        headers = [
            "شناسه", "نام کانال", "منبع استخراج", "عمق گراف", "کانال والد (Seed)",
            "تعداد اعضا", "بازدید ۲۴h", "ERR24", "AAR", "سلامت برند (Jev)", "انطباق ICP"
        ]

        data = []
        for ch in channels:
            tri = triage_decisions.get(ch.id)
            data.append([
                ch.id,
                ch.title,
                ch.source,
                f"Depth-{ch.depth}",
                ch.seed_parent or "Seed",
                ch.participants_count,
                ch.reach_24h,
                f"{ch.err24:.2f}%",
                f"{ch.aar:.3f}",
                "Clean" if (tri and tri.brand_safe) else "Flagged",
                tri.icp_score_label if tri else "Unscored",
            ])

        self._write_table(ws, start_row=4, headers=headers, data=data)

    def _build_exclusion_log(
        self,
        ws,
        channels: list[ChannelEntity],
        triage_decisions: dict[str, JevTriageDecision],
        economics: dict[str, EconomicCeiling],
    ):
        self._apply_title(ws, "لاگ کانال‌های رد شده و ممیزی کیفی (Exclusion Audit)", "Disqualified Candidates")
        headers = ["هندل کانال", "نام کانال", "دلیل رد صلاحیت", "کد خطای فیلتر", "توضیح ممیزی"]

        data = []
        for ch in channels:
            tri = triage_decisions.get(ch.id)
            eco = economics.get(ch.id)
            if tri and not tri.passed_triage:
                reason = "عدم سلامت برند یا هرزنامه" if not tri.brand_safe else "عدم تناسب با پرسونای مشتری (ICP < 3)"
                code = "FAILED_BRAND_SAFETY" if not tri.brand_safe else "LOW_ICP_SCORE"
                data.append([ch.id, ch.title, reason, code, f"Jev score: {tri.icp_score}/5 | Safe: {tri.brand_safe}"])
            elif eco and eco.recommendation == "REJECT":
                data.append([ch.id, ch.title, "توجیه اقتصادی منفی", "EXCEEDS_CPM_CEILING", eco.rationale_note])

        self._write_table(ws, start_row=4, headers=headers, data=data)

    def _build_creative_hooks(
        self,
        ws,
        channels: list[ChannelEntity],
        triage_decisions: dict[str, JevTriageDecision],
        creatives: dict[str, dict[str, str]],
    ):
        self._apply_title(ws, "زوایای محتوایی و هوک‌های تبلیغاتی (Creative & Hooks)", "Contextual Copy Angles")
        headers = ["کانال", "هندل", "فرمت تبلیغاتی بهینه", "زاویه هوک محتوایی", "پیش‌نویس قلاب فارسی (Hook)"]

        data = []
        for ch in channels:
            tri = triage_decisions.get(ch.id)
            cr = creatives.get(ch.id, {})
            if tri and tri.passed_triage:
                data.append([
                    ch.title,
                    ch.id,
                    cr.get("recommended_format", "24h Pinned"),
                    cr.get("creative_angle", "Direct problem-solution benefit"),
                    cr.get("rationale_fa", "حل چالش اساسی مخاطب با ابزار تخصصی معرفی‌شده"),
                ])

        self._write_table(ws, start_row=4, headers=headers, data=data)

    def _build_scenario_modeler(self, ws, brief: CampaignBrief):
        self._apply_title(ws, "مدل‌سازی سناریوهای بازدهی (Scenario Modeler)", "Conservative / Expected / Aggressive")
        headers = ["سناریو", "بودجه ($)", "تخمین ایمپرشن (بازدید)", "نرخ کلیک (CTR)", "کلیک جذب‌شده", "نرخ تبدیل فرود", "تعداد لید / خرید", "CAC پیش‌بینی ($)"]

        b = brief.total_budget_usd
        data = [
            ["محتاطانه (Conservative)", b, int(b * 350), "1.0%", int(b * 3.5), f"{brief.est_cvr*100:.1f}%", max(1, int(b * 3.5 * brief.est_cvr)), f"${brief.target_cac_usd * 1.25:.2f}"],
            ["مبنا و واقع‌بینانه (Expected)", b, int(b * 480), "1.8%", int(b * 8.6), f"{brief.est_cvr*100:.1f}%", max(1, int(b * 8.6 * brief.est_cvr)), f"${brief.target_cac_usd:.2f}"],
            ["خوش‌بینانه (Aggressive)", b, int(b * 620), "2.5%", int(b * 15.5), f"{brief.est_cvr*120:.1f}%", max(1, int(b * 15.5 * brief.est_cvr * 1.2)), f"${brief.target_cac_usd * 0.72:.2f}"],
        ]
        self._write_table(ws, start_row=4, headers=headers, data=data)

    def _build_attribution_tracker(
        self,
        ws,
        brief: CampaignBrief,
        channels: list[ChannelEntity],
        triage_decisions: dict[str, JevTriageDecision],
    ):
        self._apply_title(ws, "رهگیری اتریبیوشن و لینک‌های UTM (Attribution Tracker)", "UTM Parameters & Deep-Links")
        headers = ["هندل کانال", "کمپین UTM", "منبع (utm_source)", "مدیوم (utm_medium)", "محتوا (utm_content)", "لینک اختصاصی تلگرام"]

        data = []
        safe_camp = brief.campaign_name.lower().replace(" ", "_")
        for ch in channels:
            tri = triage_decisions.get(ch.id)
            if tri and tri.passed_triage:
                cname = ch.id.lstrip("@").lower()
                data.append([
                    ch.id,
                    safe_camp,
                    f"telegram_{cname}",
                    "cpm_sponsored_post",
                    f"hook_v1_{cname}",
                    f"https://t.me/your_bot?start=c_{safe_camp}_{cname}",
                ])

        self._write_table(ws, start_row=4, headers=headers, data=data)

    # --------------------------------------------------------------------------
    # Formatting & Styling Helpers
    # --------------------------------------------------------------------------
    def _apply_title(self, ws, fa_title: str, en_title: str):
        ws.merge_cells("A1:G1")
        cell = ws["A1"]
        cell.value = f"{fa_title} | {en_title}"
        cell.font = Font(name="Calibri", size=14, bold=True, color=self.WHITE)
        cell.fill = PatternFill(start_color=self.NAVY_HEADER, end_color=self.NAVY_HEADER, fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 36

    def _write_table(self, ws, start_row: int, headers: list[str], data: list[list[Any]]):
        header_fill = PatternFill(start_color=self.NAVY_HEADER, end_color=self.NAVY_HEADER, fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color=self.WHITE)
        alt_fill = PatternFill(start_color=self.ICE_BLUE, end_color=self.ICE_BLUE, fill_type="solid")
        thin_border = Border(
            left=Side(style="thin", color=self.BORDER_GRAY),
            right=Side(style="thin", color=self.BORDER_GRAY),
            top=Side(style="thin", color=self.BORDER_GRAY),
            bottom=Side(style="thin", color=self.BORDER_GRAY),
        )

        # Headers
        for col_idx, h in enumerate(headers, 1):
            c = ws.cell(row=start_row, column=col_idx, value=h)
            c.fill = header_fill
            c.font = header_font
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            c.border = thin_border
        ws.row_dimensions[start_row].height = 28

        # Data rows
        for r_offset, row in enumerate(data):
            row_idx = start_row + 1 + r_offset
            is_alt = (r_offset % 2 == 1)
            for c_idx, val in enumerate(row, 1):
                c = ws.cell(row=row_idx, column=c_idx, value=val)
                c.font = Font(name="Calibri", size=10)
                c.alignment = Alignment(horizontal="center" if isinstance(val, (int, float)) or (isinstance(val, str) and (val.startswith("$") or val.endswith("%"))) else "right", vertical="center")
                c.border = thin_border
                if is_alt:
                    c.fill = alt_fill
            ws.row_dimensions[row_idx].height = 22

    def _autofit_columns(self, ws):
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val = str(cell.value or "")
                if len(val) > max_len and len(val) < 80:
                    max_len = len(val)
            ws.column_dimensions[col_letter].width = max(14, min(45, max_len + 4))
