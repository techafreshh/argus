"""Orchestrator package: planner client and planner-visible tools."""

from argus.orchestrator.loop import run_watch
from argus.orchestrator.meta_client import Plan, get_spend, log_spend, plan, spend_total
from argus.orchestrator.planner import match_template
from argus.orchestrator.router import abstain_receipt, route
from argus.orchestrator.templates import TEMPLATE_NAMES, TEMPLATES

__all__ = [
    "TEMPLATES",
    "TEMPLATE_NAMES",
    "Plan",
    "abstain_receipt",
    "get_spend",
    "log_spend",
    "match_template",
    "plan",
    "route",
    "run_watch",
    "spend_total",
]
