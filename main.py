"""
main.py
=======
OpsGrid root entry point.

Usage:
    python main.py trigger saas_churn_prevention     # Manually trigger workflow
    python main.py dashboard                          # Live admin dashboard
    python main.py api                                # Start FastAPI server
    python main.py verify-evidence                    # View EPI artifacts
    python main.py list-workflows                     # List available workflows

This is the MANUAL SIGNAL command — trigger workflows explicitly from here.
"""

import click
import json
import os
import asyncio
from pathlib import Path


@click.group()
def cli():
    """⚡ OpsGrid — Autonomous Multi-Agent Workflow Engine"""
    pass


@cli.command()
@click.argument("workflow_name")
@click.option("--config", default="config/templates/saas.json",
              help="Path to client config JSON")
@click.option("--llm-config", default="config/templates/llm_config.json",
              help="Path to LLM config JSON")
@click.option("--signal", default="{}", help="Trigger signal as JSON string")
@click.option("--dry-run", is_flag=True, help="Validate config without running")
def trigger(workflow_name: str, config: str, llm_config: str, signal: str, dry_run: bool):
    """
    🚀 Manually trigger a workflow.

    This is the MANUAL SIGNAL — work starts when you run this command.

    Examples:
        python main.py trigger saas_churn_prevention
        python main.py trigger saas_pipeline_velocity --config config/clients/acme.json
        python main.py trigger saas_churn_prevention --signal '{"source": "manual", "priority": "high"}'
    """
    from admin.control_panel import _run_workflow_with_dashboard

    if not Path(config).exists():
        click.echo(f"❌ Config not found: {config}", err=True)
        raise SystemExit(1)

    if not Path(f"workflows/dags/{workflow_name}.json").exists():
        click.echo(f"❌ Workflow DAG not found: workflows/dags/{workflow_name}.json", err=True)
        raise SystemExit(1)

    if dry_run:
        with open(config) as f:
            cfg = json.load(f)
        click.echo(f"✓ Config valid: {cfg.get('client_name', 'unknown')}")
        click.echo(f"✓ Workflow DAG found: {workflow_name}")
        click.echo(f"✓ Active integrations: {list(cfg.get('integrations', {}).keys())}")
        return

    try:
        signal_data = json.loads(signal)
    except json.JSONDecodeError:
        click.echo("❌ Invalid signal JSON", err=True)
        raise SystemExit(1)

    signal_data.setdefault("type", "manual")
    signal_data.setdefault("source", "admin_cli")

    asyncio.run(_run_workflow_with_dashboard(
        workflow_name=workflow_name,
        config_path=config,
        llm_config_path=llm_config,
        signal_data=signal_data,
    ))


@cli.command()
@click.option("--config", default="config/templates/saas.json")
@click.option("--llm-config", default="config/templates/llm_config.json")
def dashboard(config: str, llm_config: str):
    """📊 Start the live admin dashboard."""
    from admin.control_panel import dashboard as _dashboard
    _dashboard.main(standalone_mode=False, args=["--config", config, "--llm-config", llm_config])


@cli.command()
@click.option("--host", default="0.0.0.0")
@click.option("--port", default=8000)
@click.option("--reload", is_flag=True, default=True)
def api(host: str, port: int, reload: bool):
    """🌐 Start the FastAPI server."""
    import uvicorn
    click.echo(f"Starting OpsGrid API on {host}:{port}")
    uvicorn.run("api.main:app", host=host, port=port, reload=reload)


@cli.command("list-workflows")
def list_workflows():
    """📋 List all available workflow DAGs."""
    dags_path = Path("workflows/dags")
    if not dags_path.exists():
        click.echo("No DAGs directory found.", err=True)
        return

    click.echo("\n📋 Available Workflows:\n")
    for dag_file in sorted(dags_path.glob("*.json")):
        with open(dag_file) as f:
            dag = json.load(f)
        meta = dag.get("_meta", {})
        click.echo(
            f"  ● {dag_file.stem:40s}  "
            f"[{meta.get('industry', '—'):12s}]  "
            f"{meta.get('description', '')[:60]}"
        )
    click.echo()


@cli.command("verify-evidence")
@click.option("--open-viewer", is_flag=True, help="Open latest artifact in browser")
def verify_evidence(open_viewer: bool):
    """🔒 List and verify EPI evidence artifacts."""
    from epi.epi_manager import EPIManager
    em = EPIManager()
    artifacts = em.list_artifacts()

    if not artifacts:
        click.echo("No evidence artifacts found in ./evidence/")
        return

    click.echo(f"\n🔒 Evidence Artifacts ({len(artifacts)} found):\n")
    for a in artifacts:
        click.echo(f"  {a['filename']:60s}  {a['size_kb']:6.1f} KB  {a['created'][:16]}")

    if open_viewer and artifacts:
        asyncio.run(em.view_artifact(artifacts[0]["path"]))
        click.echo(f"\nOpened: {artifacts[0]['filename']}")


@cli.command("check-config")
@click.argument("config_path")
def check_config(config_path: str):
    """✅ Validate a client config JSON file."""
    try:
        with open(config_path) as f:
            cfg = json.load(f)

        required_fields = ["client_name", "industry", "active_workflows",
                           "integrations", "business_rules", "tone_profile"]
        missing = [f for f in required_fields if f not in cfg]

        if missing:
            click.echo(f"❌ Missing required fields: {missing}", err=True)
            raise SystemExit(1)

        click.echo(f"\n✅ Config valid: {config_path}\n")
        click.echo(f"  Client:     {cfg['client_name']}")
        click.echo(f"  Industry:   {cfg['industry']}")
        click.echo(f"  Workflows:  {', '.join(cfg['active_workflows'])}")
        click.echo(f"  Integrations: {', '.join(k for k, v in cfg['integrations'].items() if v.get('enabled'))}")
        click.echo(f"  LLM Overrides: {cfg.get('llm_overrides', {})}")
        click.echo()

        # Check for unmodified template placeholders
        cfg_str = json.dumps(cfg)
        if "[MODIFY]" in cfg_str:
            count = cfg_str.count("[MODIFY]")
            click.echo(f"  ⚠️  {count} fields still have [MODIFY] placeholder — update before production\n")

    except FileNotFoundError:
        click.echo(f"❌ File not found: {config_path}", err=True)
        raise SystemExit(1)
    except json.JSONDecodeError as e:
        click.echo(f"❌ Invalid JSON: {e}", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
