"""
admin/control_panel.py
======================
Rich terminal dashboard for real-time monitoring of OpsGrid.

Shows:
  - Live workflow status and current node
  - Per-agent token usage and cost (in real-time during execution)
  - Total cost tracker
  - Admin controls: pause, stop, resume, trigger workflows

Run: python -m admin.control_panel
Or: python main.py admin

CONSTANT — do not modify for business customization.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
import uuid
import click
from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

console = Console()

# Color scheme
C_GREEN  = "green"
C_YELLOW = "yellow"
C_RED    = "bright_red"
C_BLUE   = "blue"
C_CYAN   = "cyan"
C_DIM    = "dim"
C_BOLD   = "bold"

STATUS_COLORS = {
    "running":   C_GREEN,
    "paused":    C_YELLOW,
    "escalated": C_YELLOW,
    "completed": C_GREEN,
    "failed":    C_RED,
    "stopped":   C_RED,
    "pending":   C_DIM,
}


class OpsGridDashboard:
    """
    Live terminal dashboard. Updates every N seconds showing:
    - Active workflow status
    - Real-time LLM token + cost breakdown
    - Recent escalations
    - Admin command history
    """

    def __init__(self, llm_router=None, state_manager=None, orchestrator=None):
        self._llm = llm_router
        self._state = state_manager
        self._orch = orchestrator
        self._running = True
        self._active_runs: dict[str, dict] = {}   # run_id -> metadata
        self._command_log: list[str] = []
        self._refresh_rate = int(os.getenv("ADMIN_REFRESH_RATE", "2"))

    # ─────────────────────────────────────────────────────────────────────
    # Main display
    # ─────────────────────────────────────────────────────────────────────

    def build_layout(self) -> Layout:
        """Build the full dashboard layout."""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=4),
            Layout(name="body"),
            Layout(name="footer", size=6),
        )
        layout["body"].split_row(
            Layout(name="left", ratio=3),
            Layout(name="right", ratio=2),
        )
        layout["left"].split_column(
            Layout(name="workflows", ratio=2),
            Layout(name="tokens", ratio=2),
        )
        return layout

    def render_header(self) -> Panel:
        """Top banner."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        total_cost = self._get_total_cost()
        return Panel(
            Text.from_markup(
                f"[bold cyan]⚡ OpsGrid[/bold cyan]  [dim]Autonomous Multi-Agent Workflow Engine[/dim]"
                f"    [{C_GREEN}]●[/{C_GREEN}] LIVE    "
                f"[dim]{now}[/dim]    "
                f"[yellow]Session Cost: ${total_cost:.4f}[/yellow]"
            ),
            box=box.HEAVY,
            style="cyan",
        )

    def render_workflow_table(self) -> Panel:
        """Active workflow instances."""
        table = Table(
            title="Active Workflows",
            box=box.SIMPLE_HEAD,
            expand=True,
            title_style=C_BOLD,
        )
        table.add_column("Run ID",     style=C_DIM,   no_wrap=True, width=10)
        table.add_column("Workflow",   style=C_CYAN,  no_wrap=True)
        table.add_column("Tenant",     style="white", no_wrap=True)
        table.add_column("Status",     no_wrap=True)
        table.add_column("Node",       style=C_DIM,   no_wrap=True)
        table.add_column("Cost",       style=C_YELLOW, justify="right")
        table.add_column("Elapsed",    style=C_DIM,   justify="right")

        for run_id, meta in self._active_runs.items():
            status = meta.get("status", "running")
            color = STATUS_COLORS.get(status, "white")
            elapsed = self._format_elapsed(meta.get("started_at", time.time()))

            table.add_row(
                run_id[:8],
                meta.get("workflow", "—"),
                meta.get("tenant", "—")[:20],
                Text(f"● {status}", style=color),
                meta.get("current_node", "—"),
                f"${meta.get('cost', 0.0):.4f}",
                elapsed,
            )

        if not self._active_runs:
            table.add_row(
                "—", "No active workflows", "—",
                Text("○ idle", style=C_DIM), "—", "—", "—"
            )

        return Panel(table, border_style=C_BLUE)

    def render_token_table(self) -> Panel:
        """Real-time token and cost breakdown per agent."""
        table = Table(
            title="⚡ LLM Token Usage & Cost (Live)",
            box=box.SIMPLE_HEAD,
            expand=True,
            title_style=C_BOLD,
        )
        table.add_column("Agent",       style=C_CYAN)
        table.add_column("Model",       style=C_DIM,    no_wrap=True)
        table.add_column("Calls",       justify="right")
        table.add_column("Tokens In",   justify="right", style="green")
        table.add_column("Tokens Out",  justify="right", style="blue")
        table.add_column("Cost (USD)",  justify="right", style=C_YELLOW)

        stats = self._get_llm_stats()
        total_in = 0
        total_out = 0
        total_cost = 0.0

        for row in stats.get("by_agent_rows", []):
            table.add_row(
                row["agent"],
                row["model"][-30:] if len(row["model"]) > 30 else row["model"],
                str(row["calls"]),
                row["tokens_in"],
                row["tokens_out"],
                row["cost"],
            )
            total_in += int(row["tokens_in"].replace(",", ""))
            total_out += int(row["tokens_out"].replace(",", ""))
            total_cost += float(row["cost"].replace("$", ""))

        table.add_section()
        table.add_row(
            Text("TOTAL", style=C_BOLD),
            "—",
            str(stats.get("total_calls", 0)),
            Text(f"{total_in:,}", style=f"bold {C_GREEN}"),
            Text(f"{total_out:,}", style=f"bold {C_BLUE}"),
            Text(f"${total_cost:.4f}", style=f"bold {C_YELLOW}"),
        )

        return Panel(table, border_style=C_YELLOW)

    def render_evidence_panel(self) -> Panel:
        """Recent EPI artifacts."""
        try:
            from epi.epi_manager import EPIManager
            em = EPIManager()
            artifacts = em.list_artifacts()[:5]
        except Exception:
            artifacts = []

        content = ""
        for a in artifacts:
            content += f"[cyan]{a['filename']}[/cyan]  [dim]{a['size_kb']}KB  {a['created'][:16]}[/dim]\n"

        if not content:
            content = "[dim]No .epi evidence files yet[/dim]"

        return Panel(
            Text.from_markup(content),
            title="Evidence Artifacts (.epi)",
            border_style=C_DIM,
        )

    def render_command_log(self) -> Panel:
        """Recent admin commands."""
        lines = self._command_log[-8:]
        content = "\n".join(
            f"[dim]{l}[/dim]" if "> " in l else f"[green]{l}[/green]"
            for l in lines
        ) or "[dim]No commands yet. Press [bold]?[/bold] for help.[/dim]"
        return Panel(
            Text.from_markup(content),
            title="Admin Commands",
            border_style=C_DIM,
        )

    def render_footer(self) -> Panel:
        """Footer with keyboard shortcuts."""
        shortcuts = (
            "[cyan][T][/cyan] Trigger Workflow  "
            "[cyan][P][/cyan] Pause  "
            "[cyan][R][/cyan] Resume  "
            "[cyan][S][/cyan] Stop  "
            "[cyan][E][/cyan] View Evidence  "
            "[cyan][Q][/cyan] Quit"
        )
        return Panel(Text.from_markup(shortcuts), style=C_DIM)

    def update_layout(self, layout: Layout) -> None:
        """Refresh all layout panels."""
        layout["header"].update(self.render_header())
        layout["workflows"].update(self.render_workflow_table())
        layout["tokens"].update(self.render_token_table())
        layout["right"].update(
            Layout(name="evidence_cmd")
        )
        layout["right"].split_column(
            Layout(self.render_evidence_panel(), name="evidence"),
            Layout(self.render_command_log(), name="commands"),
        )
        layout["footer"].update(self.render_footer())

    # ─────────────────────────────────────────────────────────────────────
    # Admin commands (used by CLI)
    # ─────────────────────────────────────────────────────────────────────

    def register_run(self, run_id: str, workflow: str, tenant: str) -> None:
        self._active_runs[run_id] = {
            "workflow": workflow,
            "tenant": tenant,
            "status": "running",
            "current_node": "starting",
            "cost": 0.0,
            "started_at": time.time(),
        }

    def update_run(self, run_id: str, **kwargs) -> None:
        if run_id in self._active_runs:
            self._active_runs[run_id].update(kwargs)

    def complete_run(self, run_id: str, status: str = "completed") -> None:
        if run_id in self._active_runs:
            self._active_runs[run_id]["status"] = status

    def log_command(self, cmd: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self._command_log.append(f"[{ts}] {cmd}")

    # ─────────────────────────────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────────────────────────────

    def _get_llm_stats(self) -> dict:
        if self._llm:
            stats = self._llm.get_live_stats()
            return {
                "total_calls": stats["total_calls"],
                "total_tokens_in": stats["total_tokens_in"],
                "total_tokens_out": stats["total_tokens_out"],
                "total_cost_usd": stats["total_cost_usd"],
                "by_agent_rows": self._llm.get_cost_table_rows(),
            }
        return {"total_calls": 0, "by_agent_rows": []}

    def _get_total_cost(self) -> float:
        if self._llm:
            return self._llm.get_live_stats().get("total_cost_usd", 0.0)
        return 0.0

    @staticmethod
    def _format_elapsed(started_at: float) -> str:
        elapsed = int(time.time() - started_at)
        if elapsed < 60:
            return f"{elapsed}s"
        return f"{elapsed // 60}m {elapsed % 60}s"


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

@click.group()
def cli():
    """OpsGrid Admin Control Panel"""
    pass


@cli.command()
@click.option("--config", default="config/templates/saas.json", help="Client config JSON path")
@click.option("--llm-config", default="config/templates/llm_config.json", help="LLM config path")
def dashboard(config: str, llm_config: str):
    """Start the live admin dashboard."""
    from core.llm_router import LLMRouter
    from core.state_manager import StateManager

    console.print(Panel.fit(
        "[bold cyan]OpsGrid Admin Dashboard[/bold cyan]\n"
        "[dim]Initializing systems...[/dim]",
        border_style="cyan"
    ))

    llm_router = LLMRouter(config_path=llm_config)
    dashboard = OpsGridDashboard(llm_router=llm_router)
    layout = dashboard.build_layout()

    with Live(layout, console=console, refresh_per_second=0.5, screen=True) as live:
        try:
            while True:
                dashboard.update_layout(layout)
                time.sleep(dashboard._refresh_rate)
        except KeyboardInterrupt:
            pass

    console.print("[green]Dashboard closed.[/green]")


@cli.command()
@click.argument("workflow_name")
@click.option("--config", default="config/templates/saas.json", help="Client config JSON")
@click.option("--llm-config", default="config/templates/llm_config.json")
@click.option("--signal", default='{}', help="Trigger signal JSON string")
def trigger(workflow_name: str, config: str, llm_config: str, signal: str):
    """
    Manually trigger a workflow. This is the MANUAL SIGNAL.

    Example:
        python main.py trigger saas_churn_prevention --config config/templates/saas.json
    """
    import asyncio

    console.print(Panel.fit(
        f"[bold green]⚡ Triggering Workflow[/bold green]\n"
        f"[cyan]Workflow:[/cyan] {workflow_name}\n"
        f"[cyan]Config:[/cyan] {config}",
        border_style="green"
    ))

    confirmed = Confirm.ask(
        f"[yellow]Start workflow [bold]{workflow_name}[/bold]?[/yellow]",
        default=True
    )
    if not confirmed:
        console.print("[dim]Cancelled.[/dim]")
        return

    asyncio.run(_run_workflow_with_dashboard(
        workflow_name=workflow_name,
        config_path=config,
        llm_config_path=llm_config,
        signal_data=json.loads(signal),
    ))


async def _run_workflow_with_dashboard(
    workflow_name: str,
    config_path: str,
    llm_config_path: str,
    signal_data: dict,
) -> None:
    """Run a workflow and show live progress in the terminal."""
    import aiofiles
    from core.llm_router import LLMRouter
    from core.state_manager import StateManager
    from core.orchestrator import WorkflowOrchestrator
    from agents.base_agent import ToolRegistry
    from epi.epi_manager import EPIManager
 
    # Load configs asynchronously to avoid blocking event loop
    async with aiofiles.open(config_path) as f:
        tenant_config = json.loads(await f.read())
    async with aiofiles.open(llm_config_path) as f:
        llm_config = json.loads(await f.read())
 
    llm_router = LLMRouter(config_path=llm_config_path)
    tool_registry = ToolRegistry()
    epi_manager = EPIManager()
    state_manager = StateManager(session=None)
    orchestrator = WorkflowOrchestrator(
        state_manager=state_manager,
        llm_router=llm_router,
        tool_registry=tool_registry,
        epi_manager=epi_manager,
    )
 
    dash = OpsGridDashboard(llm_router=llm_router, state_manager=state_manager)
    run_id = str(uuid.uuid4())[:8]
    dash.register_run(run_id, workflow_name, tenant_config.get("client_name", "unknown"))
 
    layout = dash.build_layout()
    dash.log_command(f"> trigger {workflow_name}")
 
    with Live(layout, console=console, refresh_per_second=1, screen=True):
        dash.update_layout(layout)
 
        try:
            result = await orchestrator.run_workflow(
                tenant_config=tenant_config,
                workflow_name=workflow_name,
                trigger_signal=signal_data or {"type": "manual", "source": "admin_cli"},
            )
 
            status = result.get("status", "unknown")
            dash.complete_run(run_id, str(status))
            dash.log_command(f"✓ Completed: {status}")
            dash.update_layout(layout)
            await asyncio.sleep(3)  # ← FIXED: was time.sleep(3)
 
        except Exception as e:
            dash.complete_run(run_id, "failed")
            dash.log_command(f"✗ Failed: {str(e)[:60]}")
            dash.update_layout(layout)
            await asyncio.sleep(3)  # ← FIXED: was time.sleep(3)
 
    # Print final cost summary
    stats = llm_router.get_live_stats()
    console.print("\n")
    console.print(Panel(
        Text.from_markup(
            f"[bold green]✓ Workflow Complete[/bold green]: {workflow_name}\n\n"
            f"[cyan]Total Tokens In:[/cyan]  {stats['total_tokens_in']:,}\n"
            f"[cyan]Total Tokens Out:[/cyan] {stats['total_tokens_out']:,}\n"
            f"[yellow]Total Cost:[/yellow]       ${stats['total_cost_usd']:.6f}\n"
            f"[cyan]Total LLM Calls:[/cyan]  {stats['total_calls']}\n"
            f"[green]Cache Hits:[/green]       {stats.get('cache_hits', 0)}\n"
        ),
        title="Session Summary",
        border_style="green"
    ))


if __name__ == "__main__":
    cli()
