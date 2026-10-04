"""
core/event_detector.py
======================
Autonomous background event detector for SMBFlow.
Monitors runtime data sources (e.g. synthetic email inbox fixture) and triggers
batch workflows when new unprocessed events arrive.

Idempotency:
Tracks processed event IDs in PostgreSQL (processed_email_events) so the same
message is never processed in multiple batches.

Batch Execution:
Groups N detected events into ONE workflow execution run rather than N separate runs.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, List, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

import api.crud as crud
from core.database import get_raw_session

log = structlog.get_logger()

FIXTURE_PATH = Path("db/seed/data/email_messages.json")
DEFAULT_POLL_INTERVAL_SECONDS = 5.0


class EmailEventDetector:
    """
    Background worker that continuously scans for new synthetic emails
    and dispatches a single batch workflow run when new messages are found.
    """

    def __init__(
        self,
        poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
        execute_workflow_fn: Optional[Callable] = None,
        broadcast_fn: Optional[Callable] = None,
    ):
        self.poll_interval = poll_interval
        self.execute_workflow_fn = execute_workflow_fn
        self.broadcast_fn = broadcast_fn
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the background polling loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop(), name="email_event_detector")
        log.info("EmailEventDetector started", poll_interval=self.poll_interval)

    async def stop(self) -> None:
        """Gracefully stop the background polling loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        log.info("EmailEventDetector stopped")

    async def _poll_loop(self) -> None:
        """Continuous polling loop."""
        while self._running:
            try:
                await self.poll_and_dispatch()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("Error in EmailEventDetector poll cycle", error=str(e))
            
            try:
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break

    async def poll_and_dispatch(self) -> Optional[dict]:
        """
        Check for new emails in the runtime fixture and dispatch a batch workflow run
        if unprocessed emails exist. Returns dispatch summary if triggered.
        """
        if not FIXTURE_PATH.exists():
            return None

        try:
            with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
                all_messages = raw_data.get("messages", []) if isinstance(raw_data, dict) else (raw_data if isinstance(raw_data, list) else [])
        except Exception as read_err:
            log.warning("Could not read email fixture", error=str(read_err))
            return None

        if not all_messages:
            return None

        session: AsyncSession = await get_raw_session()
        async with session:
            try:
                processed_ids = await crud.get_processed_email_ids(session)
                unprocessed = [
                    m for m in all_messages
                    if isinstance(m, dict) and m.get("id") and m.get("id") not in processed_ids
                ]

                if not unprocessed:
                    return None

                unprocessed_ids = [m["id"] for m in unprocessed]
                batch_id = f"batch_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:8]}"
                run_id = str(uuid.uuid4())

                # Resolve default organization context
                from db.models.core import Organization
                from sqlalchemy import select

                res = await session.execute(select(Organization))
                orgs = res.scalars().all()

                if orgs:
                    org = orgs[0]
                    org_id = str(org.id)
                    target_tenant_id, tenant_config = await crud.resolve_tenant_config_bridge(session, org_id)
                else:
                    default_org = Organization(
                        id=uuid.uuid4(),
                        name="Default Organization",
                        industry="general",
                        enabled_modules=["email_summarizer"],
                        profile_config={},
                        active=True,
                    )
                    session.add(default_org)
                    await session.flush()
                    org_id = str(default_org.id)
                    target_tenant_id, tenant_config = await crud.resolve_tenant_config_bridge(session, org_id)

                log.info(
                    "Detected new email batch",
                    batch_id=batch_id,
                    new_email_count=len(unprocessed_ids),
                    run_id=run_id,
                    tenant_id=target_tenant_id,
                )

                # Record processed emails upfront in DB to prevent concurrent duplicate batches
                await crud.record_processed_emails(
                    session,
                    message_ids=unprocessed_ids,
                    batch_id=batch_id,
                    instance_id=run_id,
                    organization_id=str(org_id) if org_id else None,
                    source="synthetic_fixture",
                )

                # Create workflow instance
                trigger_signal = {
                    "event_type": "new_email_batch",
                    "batch_id": batch_id,
                    "message_ids": unprocessed_ids,
                    "email_count": len(unprocessed_ids),
                    "source": "event_detector",
                    "timestamp": datetime.utcnow().isoformat(),
                }

                await crud.create_workflow_instance(
                    session,
                    run_id=run_id,
                    tenant_id=target_tenant_id,
                    workflow_name="email_summarizer",
                    trigger_signal=trigger_signal,
                    triggered_by="event_detector",
                    tenant_config=tenant_config,
                )

                budget = await crud.get_budget_settings(session, target_tenant_id) or {}
                await session.commit()

                # Dispatch background workflow execution
                if self.execute_workflow_fn:
                    asyncio.create_task(
                        self.execute_workflow_fn(
                            run_id,
                            tenant_config,
                            "email_summarizer",
                            trigger_signal,
                            budget,
                        )
                    )
                else:
                    # Direct invocation fallback using orchestrator
                    from api.main import _execute_workflow_background
                    asyncio.create_task(
                        _execute_workflow_background(
                            run_id,
                            tenant_config,
                            "email_summarizer",
                            trigger_signal,
                            budget,
                        )
                    )

                if self.broadcast_fn:
                    await self.broadcast_fn(
                        "workflow_triggered",
                        {
                            "run_id": run_id,
                            "workflow": "email_summarizer",
                            "tenant_id": target_tenant_id,
                            "batch_id": batch_id,
                            "email_count": len(unprocessed_ids),
                            "triggered_by": "event_detector",
                        },
                    )

                return {
                    "batch_id": batch_id,
                    "run_id": run_id,
                    "email_count": len(unprocessed_ids),
                    "message_ids": unprocessed_ids,
                }

            except Exception as dispatch_err:
                await session.rollback()
                log.error("Failed to dispatch batch workflow", error=str(dispatch_err))
                raise dispatch_err
