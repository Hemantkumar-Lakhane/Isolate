"""
core/config_validator.py
========================
Runtime validation of tenant configs before any workflow trigger.

Catches:
  1. Unreplaced [MODIFY] / REPLACE_WITH_UUID template placeholders
  2. Missing required top-level fields
  3. Invalid business rule values (negative weights, impossible thresholds)
  4. Industry-specific compliance rule enforcement
  5. Active workflow names that don't map to real DAG files

Called by orchestrator BEFORE the first node executes.
Also exposed via API: POST /api/v1/tenants/{tenant_id}/validate-config

CONSTANT — do not modify for business customization.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import structlog

log = structlog.get_logger()

import os as _os
_PROJECT_ROOT = Path(_os.getenv("OPSGRID_ROOT", Path(__file__).parent.parent))
DAGS_DIR = _PROJECT_ROOT / "workflows" / "dags"
_PROMPTS_DIR = _PROJECT_ROOT / "workflows" / "prompts"  # used by auto_eval too


@dataclass
class ValidationIssue:
    severity: str    # "error" | "warning"
    field: str
    message: str
    value: Optional[str] = None


@dataclass
class ConfigValidationResult:
    valid: bool = True
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)

    def add_error(self, field: str, msg: str, value: str = None) -> None:
        self.errors.append(ValidationIssue("error", field, msg, str(value)[:80] if value else None))
        self.valid = False

    def add_warning(self, field: str, msg: str, value: str = None) -> None:
        self.warnings.append(ValidationIssue("warning", field, msg, str(value)[:80] if value else None))

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "errors": [{"field": e.field, "message": e.message, "value": e.value} for e in self.errors],
            "warnings": [{"field": w.field, "message": w.message, "value": w.value} for w in self.warnings],
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
        }



def _find_placeholder_fields(obj, path: str = "") -> list[str]:
    """
    Recursively walk a config object and return all field paths that contain
    [MODIFY] or REPLACE_WITH_UUID placeholders.
    
    Returns a list of dot-notation field paths, e.g.:
      ["integrations.hubspot.credential_id", "client_name"]
    """
    findings: list[str] = []
    if isinstance(obj, dict):
        for key, val in obj.items():
            child_path = f"{path}.{key}" if path else key
            findings.extend(_find_placeholder_fields(val, child_path))
    elif isinstance(obj, list):
        for i, val in enumerate(obj):
            findings.extend(_find_placeholder_fields(val, f"{path}[{i}]"))
    elif isinstance(obj, str):
        if "[MODIFY]" in obj or "REPLACE_WITH_UUID" in obj:
            findings.append(path)
    return findings


def _get_nested(obj, dotpath: str, default=None):
    """Safely retrieve a nested value using dot-notation path."""
    try:
        parts = dotpath.replace("[", ".").replace("]", "").split(".")
        current = obj
        for part in parts:
            if part.isdigit():
                current = current[int(part)]
            elif isinstance(current, dict):
                current = current[part]
            else:
                return default
        return current
    except (KeyError, IndexError, TypeError):
        return default

def validate_tenant_config(config: dict, strict: bool = False) -> ConfigValidationResult:
    """
    Validate a tenant config JSON before workflow execution.
    """
    result = ConfigValidationResult()
    config_str = json.dumps(config)

    # Industry must be initialized before any validation checks
    industry = config.get("industry", "").lower()

    # ── 1. Template placeholder check ────────────────────────────────────
    placeholder_fields = _find_placeholder_fields(config)
    if placeholder_fields:
        # Split by placeholder type for a more actionable error message
        modify_fields = [f for f in placeholder_fields
                         if isinstance(_get_nested(config, f), str)
                         and "[MODIFY]" in _get_nested(config, f, "")]
        uuid_fields = [f for f in placeholder_fields
                       if isinstance(_get_nested(config, f), str)
                       and "REPLACE_WITH_UUID" in _get_nested(config, f, "")]
 
        if modify_fields:
            result.add_error(
                "template_placeholders",
                f"Found {len(modify_fields)} unreplaced [MODIFY] placeholder(s) in: "
                f"{', '.join(modify_fields[:8])}"
                + (f" ... and {len(modify_fields)-8} more" if len(modify_fields) > 8 else ""),
            )
        if uuid_fields:
            result.add_error(
                "template_placeholders",
                f"Found {len(uuid_fields)} unreplaced REPLACE_WITH_UUID placeholder(s) in: "
                f"{', '.join(uuid_fields[:8])}. "
                f"Store credentials via POST /api/v1/credentials and use the returned credential_id.",
            )

    # ── 2. Required top-level fields ──────────────────────────────────────
    REQUIRED_FIELDS = {
        "client_name": "Company name",
        "industry": "Industry vertical",
        "business_rules": "Business rules configuration",
        "tone_profile": "Tone profile",
        "action_library": "Action library",
    }
    for key, label in REQUIRED_FIELDS.items():
        if not config.get(key):
            result.add_error(key, f"Required field '{label}' ({key}) is missing or empty.")

    # ── 3. Business rules validation ──────────────────────────────────────
    br = config.get("business_rules") or {}

    confidence_threshold = br.get("confidence_threshold")
    if confidence_threshold is not None:
        try:
            ct = float(confidence_threshold)
            if not (0.0 <= ct <= 1.0):
                result.add_error(
                    "business_rules.confidence_threshold",
                    f"confidence_threshold must be between 0.0 and 1.0, got {ct}",
                    str(ct),
                )
        except (TypeError, ValueError):
            result.add_error(
                "business_rules.confidence_threshold",
                f"confidence_threshold must be a number, got: {type(confidence_threshold).__name__}",
            )

    # Churn risk weights should sum to ~1.0 (SaaS-specific check)
    churn = br.get("churn_risk") or {}
    weight_keys = ["usage_drop_weight", "support_spike_weight", "nps_weight", "engagement_recency_weight"]
    if industry == "saas" and all(k in churn for k in weight_keys):
        total = sum(float(churn.get(k, 0)) for k in weight_keys)
        if not (0.95 <= total <= 1.05):
            result.add_warning(
                "business_rules.churn_risk",
                f"Churn risk weights sum to {total:.2f} — they should sum to 1.0. "
                "This may skew churn scores.",
                str(total),
            )

    # Escalation SLA should be positive
    esc = br.get("escalation") or {}
    sla = esc.get("sla_hours")
    if sla is not None:
        try:
            if float(sla) <= 0:
                result.add_error("business_rules.escalation.sla_hours", f"sla_hours must be positive, got {sla}")
        except (TypeError, ValueError):
            result.add_error("business_rules.escalation.sla_hours", "sla_hours must be a number")

    # ── 4. Active workflows must have DAG files ───────────────────────────
    active_workflows = config.get("active_workflows", [])
    if not active_workflows:
        result.add_warning("active_workflows", "No active workflows configured. Nothing will run.")
    else:
        for wf in active_workflows:
            dag_path = DAGS_DIR / f"{wf}.json"
            if not dag_path.exists():
                result.add_error(
                    "active_workflows",
                    f"Workflow '{wf}' is listed as active but has no DAG file at "
                    f"workflows/dags/{wf}.json. Create the DAG or remove this workflow.",
                    wf,
                )

    # ── 5. Tone profile completeness ─────────────────────────────────────
    tone = config.get("tone_profile") or {}
    if not tone.get("brand_voice"):
        result.add_warning("tone_profile.brand_voice", "No brand_voice defined — Drafting Agent will use generic tone.")
    if not tone.get("sign_off_name"):
        result.add_warning("tone_profile.sign_off_name", "No sign_off_name — emails will have no sender name.")

    # ── 6. Action library must be non-empty ──────────────────────────────
    action_lib = config.get("action_library") or {}
    if isinstance(action_lib, dict) and len(action_lib) == 0:
        result.add_error("action_library", "Action library is empty — Reasoning Agent cannot recommend any actions.")
    elif isinstance(action_lib, dict) and "_comment" in action_lib and len(action_lib) == 1:
        result.add_error("action_library", "Action library only contains a comment — no real actions defined.")

    if industry == "healthcare":
        compliance = br.get("compliance") or {}
        if not compliance.get("hipaa_mode"):
            result.add_warning(
                "business_rules.compliance.hipaa_mode",
                "Healthcare industry config should set hipaa_mode=true to enforce HIPAA constraints.",
            )
        if not compliance.get("no_clinical_details_in_outreach"):
            result.add_warning(
                "business_rules.compliance.no_clinical_details_in_outreach",
                "Healthcare workflows should set no_clinical_details_in_outreach=true.",
            )

    if industry == "finance":
        anomaly = br.get("anomaly_detection") or {}
        if not anomaly:
            result.add_warning(
                "business_rules.anomaly_detection",
                "Finance config missing anomaly_detection rules — expense monitoring will use defaults.",
            )
            
    if industry == "real_estate":
        compliance = br.get("compliance") or {}
        # Fair Housing Act is a hard legal requirement — blocking error if absent
        if not compliance.get("fair_housing_mode"):
            result.add_error(
                "business_rules.compliance.fair_housing_mode",
                "Real estate configs MUST set fair_housing_mode=true. "
                "The VerificationAgent enforces Fair Housing Act compliance on all "
                "AI-drafted communications. Without this, the system cannot block "
                "discriminatory language in generated content.",
            )
        if not compliance.get("require_broker_approval_above_usd") and not compliance.get("require_broker_approval"):
            result.add_warning(
                "business_rules.compliance.require_broker_approval_above_usd",
                "Real estate configs should define require_broker_approval_above_usd "
                "to gate high-value actions (e.g. offers > $1M) on broker sign-off.",
            )
        # Subtype check
        subtype = config.get("real_estate_subtype", "")
        if not subtype:
            result.add_warning(
                "real_estate_subtype",
                "Set real_estate_subtype to 'brokerage' or 'property_management' "
                "so the correct workflows and prompts are selected.",
            )

    # ── 8. Integration credential placeholder check ───────────────────────
    integrations = config.get("integrations") or {}
    for int_name, int_conf in integrations.items():
        if not isinstance(int_conf, dict):
            continue
        if int_conf.get("enabled") and not int_conf.get("credential_id"):
            result.add_warning(
                f"integrations.{int_name}",
                f"Integration '{int_name}' is enabled but has no credential_id. "
                "It will fall back to local dev tools.",
            )

    # ── 9. Client ID must be a real UUID (not placeholder) ───────────────
    client_id = config.get("client_id", "")
    if "REPLACE" in str(client_id).upper() or not client_id:
        result.add_warning(
            "client_id",
            "client_id is missing or a placeholder — tenant isolation may not work correctly.",
        )

    # Strict mode: promote warnings to errors
    if strict and result.warnings:
        for w in result.warnings:
            result.errors.append(ValidationIssue("error", w.field, f"[STRICT] {w.message}", w.value))
        result.valid = len(result.errors) == 0

    if result.valid:
        log.info(
            "Config validation passed",
            client=config.get("client_name", "?"),
            industry=industry,
            warnings=len(result.warnings),
        )
    else:
        log.warning(
            "Config validation FAILED",
            client=config.get("client_name", "?"),
            errors=len(result.errors),
            warnings=len(result.warnings),
        )

    return result