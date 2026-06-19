"""Azure Monitor Metrics adapter for Foundry/Azure OpenAI dashboards."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List
from urllib.parse import quote

import httpx

from backend.app.config import settings


class AzureMonitorConfigError(RuntimeError):
    """Raised when Azure Monitor settings or credentials are incomplete."""


@dataclass(frozen=True)
class MonitorMetricPoint:
    """Normalized metric value returned to the admin dashboard."""

    name: str
    total: float = 0.0
    average: float = 0.0
    maximum: float = 0.0
    count: int = 0


class AzureMonitorMetricsClient:
    """Fetch Azure Monitor metrics for the configured Foundry/OpenAI resource."""

    def __init__(
        self,
        resource_id: str = "",
        metric_names: str = "",
        api_version: str = "",
        timespan_minutes: int = 0,
        token_limit: int = 0,
    ) -> None:
        self.resource_id = resource_id or settings.azure_monitor_resource_id
        self.metric_names = metric_names or settings.azure_monitor_metric_names
        self.api_version = api_version or settings.azure_monitor_api_version
        self.timespan_minutes = timespan_minutes or settings.azure_monitor_timespan_minutes
        self.token_limit = token_limit or settings.azure_monitor_token_limit

    def dashboard_summary(self) -> dict:
        """Return a safe, UI-ready monitoring summary."""
        if not self.resource_id:
            return {
                "status": "not_configured",
                "configured": False,
                "resource": "",
                "request_count": 0,
                "tokens_used": 0,
                "token_limit": self.token_limit,
                "latency_ms": 0,
                "error_count": 0,
                "throttled_count": 0,
                "model_load_percent": 0,
                "metric_names": _metric_names(self.metric_names),
                "message": "AZURE_MONITOR_RESOURCE_ID is not configured.",
            }
        try:
            metrics = self.fetch()
        except (AzureMonitorConfigError, httpx.HTTPError, ValueError, KeyError) as exc:
            return {
                "status": "unavailable",
                "configured": True,
                "resource": _resource_label(self.resource_id),
                "request_count": 0,
                "tokens_used": 0,
                "token_limit": self.token_limit,
                "latency_ms": 0,
                "error_count": 0,
                "throttled_count": 0,
                "model_load_percent": 0,
                "metric_names": _metric_names(self.metric_names),
                "message": _safe_message(exc),
            }
        normalized = _normalize_metrics(metrics, token_limit=self.token_limit)
        return {
            "status": "connected",
            "configured": True,
            "resource": _resource_label(self.resource_id),
            "metric_names": _metric_names(self.metric_names),
            **normalized,
        }

    def fetch(self) -> List[MonitorMetricPoint]:
        """Call Azure Monitor Metrics REST API and return normalized points."""
        self._validate()
        headers = {"Authorization": f"Bearer {_azure_cli_token()}"}
        response = httpx.get(
            self._url(),
            headers=headers,
            params=self._params(),
            timeout=15,
        )
        response.raise_for_status()
        body = response.json()
        values = body.get("value", [])
        if not isinstance(values, list):
            raise ValueError("Azure Monitor response did not include a metric list.")
        return [_metric_point(item) for item in values if isinstance(item, dict)]

    def _url(self) -> str:
        encoded = quote(self.resource_id.strip("/"), safe="/")
        return f"https://management.azure.com/{encoded}/providers/Microsoft.Insights/metrics"

    def _params(self) -> Dict[str, str]:
        end = datetime.now(timezone.utc).replace(microsecond=0)
        start = end - timedelta(minutes=max(1, self.timespan_minutes))
        return {
            "api-version": self.api_version,
            "metricnames": ",".join(_metric_names(self.metric_names)),
            "timespan": f"{_iso_z(start)}/{_iso_z(end)}",
            "interval": "PT5M",
            "aggregation": "Total,Average,Maximum,Count",
        }

    def _validate(self) -> None:
        if not self.resource_id:
            raise AzureMonitorConfigError("AZURE_MONITOR_RESOURCE_ID is required.")
        if not _metric_names(self.metric_names):
            raise AzureMonitorConfigError("AZURE_MONITOR_METRIC_NAMES is required.")


def _metric_point(item: dict) -> MonitorMetricPoint:
    name_payload = item.get("name", {})
    name = ""
    if isinstance(name_payload, dict):
        name = str(name_payload.get("value") or name_payload.get("localizedValue") or "")
    totals = {"total": 0.0, "average": 0.0, "maximum": 0.0, "count": 0}
    series = item.get("timeseries", [])
    if isinstance(series, list):
        for row in series:
            if not isinstance(row, dict):
                continue
            data = row.get("data", [])
            if not isinstance(data, list):
                continue
            for point in data:
                if not isinstance(point, dict):
                    continue
                totals["total"] += _float(point.get("total"))
                totals["average"] += _float(point.get("average"))
                totals["maximum"] = max(totals["maximum"], _float(point.get("maximum")))
                if point.get("count") is not None:
                    totals["count"] += int(_float(point.get("count")))
    return MonitorMetricPoint(
        name=name,
        total=totals["total"],
        average=totals["average"],
        maximum=totals["maximum"],
        count=totals["count"],
    )


def _normalize_metrics(metrics: Iterable[MonitorMetricPoint], token_limit: int) -> dict:
    tokens = 0.0
    requests = 0.0
    latency_values: List[float] = []
    errors = 0.0
    throttles = 0.0
    for metric in metrics:
        key = metric.name.lower()
        value = metric.total or metric.average or metric.maximum
        if "error" in key or "failure" in key or "failed" in key:
            errors += value
        elif "throttle" in key or "rate limit" in key:
            throttles += value
        elif "token" in key:
            tokens += value
        elif "request" in key or "call" in key:
            requests += value
        elif "latency" in key or "duration" in key:
            latency_values.append(metric.average or metric.maximum or metric.total)
    latency_ms = round(sum(latency_values) / len(latency_values), 1) if latency_values else 0
    load_percent = _percent(tokens, token_limit)
    return {
        "request_count": round(requests),
        "tokens_used": round(tokens),
        "token_limit": token_limit,
        "latency_ms": latency_ms,
        "error_count": round(errors),
        "throttled_count": round(throttles),
        "model_load_percent": load_percent,
        "message": "Azure Monitor metrics loaded.",
    }


def _azure_cli_token() -> str:
    completed = subprocess.run(
        [
            "az",
            "account",
            "get-access-token",
            "--scope",
            "https://management.azure.com/.default",
            "--query",
            "accessToken",
            "-o",
            "tsv",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    token = completed.stdout.strip()
    if completed.returncode != 0 or not token:
        raise AzureMonitorConfigError("Azure CLI management token could not be acquired.")
    return token


def _metric_names(raw: str) -> List[str]:
    return [name.strip() for name in raw.split(",") if name.strip()]


def _float(value: object) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _percent(value: float, total: int) -> int:
    if total <= 0:
        return 0
    return max(0, min(100, round((value / total) * 100)))


def _iso_z(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _resource_label(resource_id: str) -> str:
    parts = [part for part in resource_id.split("/") if part]
    if len(parts) >= 2:
        return "/".join(parts[-2:])
    return resource_id


def _safe_message(exc: Exception) -> str:
    message = str(exc) or exc.__class__.__name__
    return message.splitlines()[0][:160]
