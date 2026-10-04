"""
epi/epi_manager.py
==================
Integrates EPI recorder for tamper-evident audit trails of every workflow run.

Uses:
  - EPICallback on litellm for automatic LLM call recording
  - record() context manager for workflow-level evidence
  - agent_run() for each agent execution
  - verify after completion for trust check

Every workflow produces one .epi artifact in evidence/ directory.

CONSTANT — do not modify for business customization.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

import litellm
import structlog

log = structlog.get_logger()

# Configure EPI evidence directory
EVIDENCE_DIR = Path(os.getenv("EPI_EVIDENCE_DIR", "./evidence"))
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

# Attempt to configure EPI recorder integration
try:
    from epi_recorder.integrations.litellm import EPICallback
    from epi_recorder import record, get_current_session

    _epi_available = True
    _epi_callback = EPICallback()
    litellm.callbacks = [_epi_callback]
    log.info("EPI recorder enabled — all LLM calls will be recorded")

except ImportError:
    _epi_available = False
    log.warning("EPI recorder not installed — evidence capture disabled. Run: pip install epi-recorder")


class EPIWorkflowContext:
    """
    Context manager returned by EPIManager.record_workflow().
    Provides log_agent_run() for structured evidence capture.
    """

    def __init__(
        self,
        workflow_name: str,
        tenant_id: str,
        artifact_path: Path,
        session: Any = None,
    ):
        self.workflow_name = workflow_name
        self.tenant_id = tenant_id
        self.artifact_path = artifact_path
        self._session = session
        self._agent_steps: list[dict] = []

    async def log_agent_run(
        self,
        node_id: str,
        agent_type: str,
        input_summary: dict,
        output_summary: dict,
        confidence: Optional[float],
        reasoning: str,
        tokens_in: Optional[int] = None,
        tokens_out: Optional[int] = None,
        cost_usd: Optional[float] = None,
        model: str = "",
    ) -> None:
        """Log a single agent execution as a structured EPI step."""
        step_data = {
            "node_id": node_id,
            "agent_type": agent_type,
            "model": model,
            "timestamp": datetime.utcnow().isoformat(),
            "input_summary": input_summary,
            "output_keys": list(output_summary.keys()) if isinstance(output_summary, dict) else [],
        }
        if confidence is not None:
            step_data["confidence"] = round(confidence, 4)
        if tokens_in is not None:
            step_data["tokens_in"] = tokens_in
        if tokens_out is not None:
            step_data["tokens_out"] = tokens_out
        if cost_usd is not None:
            step_data["cost_usd"] = round(cost_usd, 6)
        self._agent_steps.append(step_data)

        if self._session and _epi_available:
            try:
                # Log as structured EPI step
                self._session.log_step(
                    f"agent.{agent_type}",
                    {
                        **step_data,
                        "reasoning_preview": reasoning[:500] if reasoning else "",
                    },
                )
            except Exception as e:
                log.warning("EPI step logging failed", error=str(e))

    def get_all_steps(self) -> list[dict]:
        return self._agent_steps


class EPIManager:
    """
    Central EPI recorder manager.
    Wraps every workflow in a .epi evidence artifact.
    """

    def __init__(self):
        self._available = _epi_available
        self._artifacts: dict[str, str] = {}   # run_id -> artifact_path

    @asynccontextmanager
    async def record_workflow(
        self, workflow_name: str, tenant_id: str
    ) -> AsyncGenerator[EPIWorkflowContext, None]:
        """
        Context manager that wraps a workflow in EPI recording.

        Usage:
            async with epi_manager.record_workflow("saas_churn", tenant_id) as ctx:
                await ctx.log_agent_run(...)
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_name = workflow_name.replace("/", "_")
        artifact_name = f"{safe_name}_{tenant_id[:8]}_{timestamp}.epi"
        artifact_path = EVIDENCE_DIR / artifact_name

        if self._available:
            try:
                with record(
                    str(artifact_path),
                    goal=f"OpsGrid workflow: {workflow_name} for tenant {tenant_id}",
                ) as epi_session:
                    try:
                        ctx = EPIWorkflowContext(
                            workflow_name=workflow_name,
                            tenant_id=tenant_id,
                            artifact_path=artifact_path,
                            session=epi_session,
                        )
                        yield ctx

                    except Exception as inner_e:
                        log.error("Workflow error during EPI recording", error=str(inner_e))
                        raise

                log.info("EPI artifact saved", path=str(artifact_path))
                self._artifacts[workflow_name] = str(artifact_path)
                await self._verify_artifact(artifact_path)

            except Exception as e:
                log.error("EPI recording failed", error=str(e))
                # Fallback: yield context without EPI
                ctx = EPIWorkflowContext(
                    workflow_name=workflow_name,
                    tenant_id=tenant_id,
                    artifact_path=artifact_path,
                    session=None,
                )
                yield ctx
        else:
            # EPI not available — yield minimal context
            ctx = EPIWorkflowContext(
                workflow_name=workflow_name,
                tenant_id=tenant_id,
                artifact_path=artifact_path,
                session=None,
            )
            yield ctx

    async def _verify_artifact(self, artifact_path: Path) -> None:
        """Run epi verify on the artifact to confirm integrity."""
        if not artifact_path.exists():
            return
        try:
            import subprocess
            result = subprocess.run(
                ["epi", "verify", str(artifact_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                log.info("EPI verification: SIGNED ✓", path=str(artifact_path))
            else:
                log.warning("EPI verification issue", stderr=result.stderr[:200])
        except Exception as e:
            log.debug("EPI verify not available", error=str(e))

    def get_artifact_path(self, workflow_name: str) -> Optional[str]:
        return self._artifacts.get(workflow_name)

    def list_artifacts(self) -> list[dict]:
        """List all evidence artifacts in the evidence directory."""
        artifacts = []
        for p in sorted(EVIDENCE_DIR.glob("*.epi"), key=lambda x: x.stat().st_mtime, reverse=True):
            artifacts.append({
                "filename": p.name,
                "path": str(p),
                "size_kb": round(p.stat().st_size / 1024, 1),
                "created": datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
            })
        return artifacts

    async def view_artifact(self, artifact_path: str) -> None:
        """Open an EPI artifact in the browser viewer."""
        if not _epi_available:
            log.warning("EPI not available — cannot view artifact")
            return
        import subprocess
        subprocess.Popen(["epi", "view", artifact_path])
        log.info("Opening EPI viewer", path=artifact_path)
