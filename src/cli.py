"""
OmniScout-TG: Interactive Campaign Brief CLI & Execution Engine
Provides an institutional terminal interface for running end-to-end media planning:
- Interactive Campaign Brief intake with smart presets
- Real-time progress updates across the 6-stage pipeline
- Rich summary tables and direct link to the generated 8-sheet Excel plan
"""

import argparse
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
from rich.theme import Theme

from config.settings import get_settings
from src.models.schemas import CampaignBrief
from src.pipeline.orchestrator import OmniScoutPipeline

custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "red",
    "success": "green",
    "bold_blue": "bold #1E40AF",
})
console = Console(theme=custom_theme)


def print_banner():
    banner_text = (
        "[bold cyan]OmniScout-TG[/bold cyan] [white]| Media-Planning Decision Intelligence Engine[/white]\n"
        "[dim]Telegram Native Recommendation Graph + b.ai System 1 Triage + 8-Sheet Excel Media Plan[/dim]"
    )
    console.print(Panel(banner_text, border_style="bold blue", expand=False))


def prompt_campaign_brief(preset: bool = False) -> CampaignBrief:
    """Collects campaign parameters interactively or returns high-conviction defaults."""
    if preset:
        console.print("[info]Using default demonstration campaign brief...[/info]")
        return CampaignBrief(
            campaign_name="Parvaz Capital Wealth Expansion",
            target_persona="Iranian retail investors, day traders, and crypto enthusiasts seeking analytical software",
            product_category="Finance & Capital Markets",
            seed_channels=["@parvazcapital_tel"],
            total_budget_usd=3000.0,
            target_cac_usd=50.0,
            est_cvr=0.02,
            est_ctr_min=0.01,
            est_ctr_max=0.025,
            risk_buffer=0.15,
        )

    console.print("\n[bold yellow]── Campaign Brief Configuration ──[/bold yellow]")

    # 1. Campaign Name
    name = console.input("[bold white]1. Campaign Name[/bold white] [dim][Parvaz Capital Wealth Expansion][/dim]: ").strip()
    name = name or "Parvaz Capital Wealth Expansion"

    # 2. Product Category
    category = console.input("[bold white]2. Industry / Category[/bold white] [dim][Finance & Capital Markets][/dim]: ").strip()
    category = category or "Finance & Capital Markets"

    # 3. Target Persona
    persona = console.input("[bold white]3. Target Persona (ICP)[/bold white] [dim][Iranian traders and crypto investors][/dim]: ").strip()
    persona = persona or "Iranian retail investors, day traders, and crypto enthusiasts seeking analytical software"

    # 4. Seed Channels
    seeds_input = console.input("[bold white]4. Seed / Anchor Channels (comma-separated)[/bold white] [dim][@parvazcapital_tel][/dim]: ").strip()
    seeds = [s.strip() for s in seeds_input.split(",") if s.strip()] if seeds_input else ["@parvazcapital_tel"]

    # 5. Budget
    budget_raw = console.input("[bold white]5. Total Budget (USD $)[/bold white] [dim][3000.0][/dim]: ").strip()
    budget = float(budget_raw) if budget_raw else 3000.0

    # 6. Target CAC
    cac_raw = console.input("[bold white]6. Target Allowable CAC (USD $)[/bold white] [dim][50.0][/dim]: ").strip()
    cac = float(cac_raw) if cac_raw else 50.0

    return CampaignBrief(
        campaign_name=name,
        target_persona=persona,
        product_category=category,
        seed_channels=seeds,
        total_budget_usd=budget,
        target_cac_usd=cac,
        est_cvr=0.02,
        est_ctr_min=0.01,
        est_ctr_max=0.025,
        risk_buffer=0.15,
    )


def display_results(result):
    """Renders structured summary tables and KPIs to the terminal."""
    console.print("\n[bold green]✓ Pipeline Execution Completed Successfully![/bold green]\n")

    # Table of Shortlisted Channels
    table = Table(
        title="OmniScout-TG: Approved Candidate Channel Portfolio",
        header_style="bold cyan",
        border_style="blue",
    )
    table.add_column("Channel Handle", style="white", justify="left")
    table.add_column("Subscribers", justify="right")
    table.add_column("24h Reach", justify="right")
    table.add_column("ERR24", justify="right")
    table.add_column("CPM Ceiling", justify="right", style="yellow")
    table.add_column("Target Bid", justify="right", style="green")
    table.add_column("Confidence", justify="center")
    table.add_column("Status", justify="center", style="bold")

    for ch in result.cluster.channels:
        eco = result.economics.get(ch.id)
        tri = result.triage_decisions.get(ch.id)
        if not eco or not tri:
            continue

        status_color = "green" if eco.recommendation == "BUY" else ("yellow" if eco.recommendation == "TEST_CELL" else "red")
        status_styled = f"[{status_color}]{eco.recommendation}[/{status_color}]"

        table.add_row(
            ch.id,
            f"{ch.participants_count:,}",
            f"{ch.reach_24h:,}",
            f"{ch.err24:.2f}%",
            f"${eco.cpm_ceiling:.2f}",
            f"${eco.bid_target_cpm:.2f}",
            f"{eco.confidence_score:.0f}%",
            status_styled,
        )

    console.print(table)

    # Execution KPI Summary Card
    stats = result.summary_stats
    summary_panel = (
        f"[bold white]Campaign Name:[/bold white] {result.brief.campaign_name}\n"
        f"[bold white]Total Discovered Graph Channels:[/bold white] {stats.get('total_discovered')}\n"
        f"[bold white]Passed System 1 Jev Triage:[/bold white] {stats.get('passed_triage')}\n"
        f"[bold white]Approved BUY Allocations:[/bold white] {stats.get('approved_buy_count')}\n"
        f"[bold white]Test Reserve Exploratory Cells:[/bold white] {stats.get('test_cell_count')}\n"
        f"[bold white]Projected Total 24h Qualified Reach:[/bold white] [bold cyan]{stats.get('total_qualified_reach'):,}[/bold cyan]\n"
        f"[bold white]Projected Customer Leads:[/bold white] [bold green]{stats.get('est_leads'):,}[/bold green]\n"
        f"[bold white]Average Recommended Target Bid:[/bold white] ${stats.get('avg_target_bid_cpm'):.2f} CPM\n\n"
        f"[bold yellow]8-Sheet RTL Excel Deliverable Generated:[/bold yellow]\n"
        f"  --> [bold underline cyan]{result.excel_path.resolve()}[/bold underline cyan]"
    )
    console.print(Panel(summary_panel, title="Media Planning Summary KPIs", border_style="green"))


def main():
    parser = argparse.ArgumentParser(description="OmniScout-TG Interactive CLI")
    parser.add_argument("--preset", action="store_true", help="Run with demonstration defaults without prompting")
    args = parser.parse_args()

    print_banner()
    settings = get_settings()

    brief = prompt_campaign_brief(preset=args.preset)

    pipeline = OmniScoutPipeline(settings=settings)

    def progress_handler(msg: str, step: int, total: int):
        console.print(f"[bold cyan][{step}/{total}][/bold cyan] {msg}")

    result = pipeline.execute(brief, progress_callback=progress_handler)
    display_results(result)


if __name__ == "__main__":
    main()
