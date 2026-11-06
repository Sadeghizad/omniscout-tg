"""
OmniScout-TG: PlusDesign (@pd_plusdesign) Round 2 Campaign Execution
Advertiser: PlusDesign (Official Executive Signature & Stamp Design)
Media Buyer: Mohammad Fazel (21 TON balance, 2.26 TON allocated budget)
Strategic Goal: Round 2 Campaign Recovery after Round 1 student channel burn.
Targeting: 100% verified live executive channels seeded from @parvazcapital_tel
Format: Image Ad + night pacing (20:00-23:00) with strict zero-tolerance live validation.
"""

import os
import sys

# Ensure UTF-8 console output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from config.settings import get_settings
from src.models.schemas import CampaignBrief
from src.pipeline.orchestrator import OmniScoutPipeline

console = Console()


def execute_plusdesign_campaign():
    settings = get_settings()

    console.print(Panel(
        "[bold cyan]OmniScout-TG: PlusDesign Round 2 Recovery Campaign[/bold cyan]\n"
        "[white]طرفین: محمد فاضل (مدیا بایر) × پلاس‌دیزاین (@pd_plusdesign - طراحی امضای رسمی)[/white]\n"
        "[dim]بودجه دور دوم: ۲.۲۶ تُن (معادل ۱.۸۸ میلیون تومان) | فرمت: عکس‌دار (Image Ad) | شیفت: ۲۰ الی ۲۳[/dim]",
        border_style="bold blue",
    ))

    # 1. Define Campaign Brief with Exact Business Constraints
    brief = CampaignBrief(
        campaign_name="PlusDesign Executive Signature Round 2",
        target_persona=(
            "مدیران عامل شرکت‌ها، کارآفرینان، بازرگانان، سرمایه‌گذاران بازار سرمایه و صاحبان بیزینس "
            "که قراردادهای حقوقی امضا می‌کنند و نیازمند امضای انحصاری، شیک، رسمی و غیرقابل جعل هستند."
        ),
        product_category="Executive Branding & Signature Design",
        seed_channels=["@parvazcapital_tel"],
        total_budget_usd=15.0,  # ~2.26 TON @ ~$6.6/TON (equivalent to remaining 1.88M Tomans)
        target_cac_usd=5.0,     # Allowable CAC for high-ticket 2.5M Toman 3-signature package
        est_cvr=0.03,           # Qualified landing page conversion rate (3%)
        est_ctr_min=0.012,      # Minimum expected CTR for image ad
        est_ctr_max=0.028,      # Maximum expected CTR for image ad
        risk_buffer=0.15,
    )

    # 2. Run Master Orchestrator Pipeline
    pipeline = OmniScoutPipeline(settings=settings)

    def log_step(msg: str, step: int, total: int):
        console.print(f"[bold cyan][{step}/{total}][/bold cyan] {msg}")

    result = pipeline.execute(brief, progress_callback=log_step)

    # 3. Display Detailed Allocation & Strategic Output
    console.print("\n[bold green]✓ اجرای پایپلاین دور دوم پلاس‌دیزاین با موفقیت انجام شد![/bold green]\n")

    # Table of Selected High-Yield Executive Channels
    table = Table(
        title="پرتفوی کانال‌های تاییدشده مدیران و تصمیم‌گیرندگان (PlusDesign Executive Selection)",
        header_style="bold cyan",
        border_style="blue",
    )
    table.add_column("کانال / هندل", style="white", justify="left")
    table.add_column("تعداد اعضا", justify="right")
    table.add_column("بازدید ۲۴ ساعته", justify="right")
    table.add_column("ERR24", justify="right")
    table.add_column("تناسب مدیریتی (RRF)", justify="center", style="bold magenta")
    table.add_column("سقف CPM (تُن)", justify="right", style="yellow")
    table.add_column("بید هدف (تُن)", justify="right", style="green")
    table.add_column("اعتبارسنجی لایو", justify="center", style="dim")
    table.add_column("وضعیت خرید", justify="center", style="bold")

    ton_rate = 6.6  # 1 TON ≈ $6.6 USD

    for ch in result.cluster.channels:
        eco = result.economics.get(ch.id)
        tri = result.triage_decisions.get(ch.id)
        if not eco or not tri:
            continue

        cpm_ton_ceil = eco.cpm_ceiling / ton_rate
        cpm_ton_bid = eco.bid_target_cpm / ton_rate

        rec_display = eco.recommendation if tri.passed_triage else "REJECTED_TRIAGE"
        status_color = "green" if rec_display == "BUY" else ("yellow" if rec_display == "TEST_CELL" else "red")
        val_status_styled = "[green]✓ تایید تلگرام[/green]" if ch.validation_status == "PUBLIC_WEB_VALIDATED" else f"[red]{ch.validation_status}[/red]"

        table.add_row(
            f"{ch.title}\n[dim]{ch.id}[/dim]",
            f"{ch.participants_count:,}",
            f"{ch.reach_24h:,}",
            f"{ch.err24:.2f}%",
            f"{ch.executive_fit_score:.1f}/100",
            f"{cpm_ton_ceil:.2f} TON",
            f"{cpm_ton_bid:.2f} TON",
            val_status_styled,
            f"[{status_color}]{rec_display}[/{status_color}]",
        )

    console.print(table)

    # Strategic Post-Mortem & Creative Angle Card
    post_mortem = (
        "[bold yellow]تحلیل آسیب‌شناسی شکست دور اول (Round 1 Root Cause):[/bold yellow]\n"
        "• [red]خطای انتخاب کانال:[/red] سوختن بودجه در کانال‌های دانشگاهی/دانشجویی وکالت و پزشکی به جای تصمیم‌گیرندگان واقعی.\n"
        "• [red]خطای هوک و کپی‌رایتینگ:[/red] استفاده از تیترهای سبک و فاقد اعتبار مثل «امضاتون دیده نمیشه؟» و «امضای خاص تو 🔥».\n"
        "• [red]عدم استفاده از تصویر:[/red] امضا ماهیت بصری دارد و تبلیغ متنی تلگرام ادز بدون عکس نمی‌توانست تمایز پلاس‌دیزاین را نشان دهد.\n\n"
        "[bold green]راهکار اصلاحی دور دوم (Round 2 Strategy):[/bold green]\n"
        "• [green]کانال‌های اقتصادی پرستیژ:[/green] تمرکز روی کانال‌های سرمایه‌گذاری و مدیران (نظیر پرواز کاپیتال، اتاق‌های بازرگانی و اخبار اقتصادی).\n"
        "• [green]فرمت عکس‌دار (Image Ad):[/green] درج تصویر اختصاصی مقایسه امضای معمولی با امضای مدیریتی و مهر لوکس پلاس‌دیزاین.\n"
        "• [green]زمان‌بندی شبانه (۲۰ الی ۲۳):[/green] حضور فعال مدیران در تلگرام بعد از ساعات کاری جلسات اداری.\n"
        "• [green]مدیریت CPM و سقف بودجه:[/green] تعیین بید هوشمند تا ۰.۳۸ تُن به دلیل رقابت، با هدف جذب لید باکیفیت به جای بازدید بیهوده.\n"
        "• [green]اعتبارسنجی ۱۰۰٪ زنده:[/green] الزام به حداقل ۱,۰۰۰ عضو و پست فعال در ۱۴ روز اخیر بدون هرگونه کانال فیک.\n\n"
        f"[bold cyan]فایل اکسل ۸ شیته گزارش کامل و اتریبیوشن:[/bold cyan]\n"
        f"  --> [bold underline]{result.excel_path.resolve()}[/bold underline]\n"
        f"[bold cyan]فایل CSV خروجی قابل تحلیل:[/bold cyan]\n"
        f"  --> [bold underline]{result.csv_path.resolve()}[/bold underline]"
    )
    console.print(Panel(post_mortem, title="گزارش استراتژیک کمپین پلاس‌دیزاین", border_style="yellow"))
    return result


if __name__ == "__main__":
    execute_plusdesign_campaign()
