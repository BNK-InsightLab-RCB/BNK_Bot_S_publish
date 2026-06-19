from backend.app.monitoring.azure_monitor import (
    AzureMonitorMetricsClient,
    MonitorMetricPoint,
    _metric_point,
    _normalize_metrics,
)


def test_azure_monitor_dashboard_summary_without_resource_id():
    summary = AzureMonitorMetricsClient(resource_id="", token_limit=5000).dashboard_summary()

    assert summary["status"] == "not_configured"
    assert summary["configured"] is False
    assert summary["token_limit"] == 5000
    assert summary["request_count"] == 0


def test_azure_monitor_metric_point_parses_timeseries():
    payload = {
        "name": {"value": "GeneratedTokens"},
        "timeseries": [
            {
                "data": [
                    {"total": 10, "average": 5, "maximum": 7, "count": 2},
                    {"total": 20, "average": 10, "maximum": 12, "count": 2},
                ]
            }
        ],
    }

    point = _metric_point(payload)

    assert point.name == "GeneratedTokens"
    assert point.total == 30
    assert point.average == 15
    assert point.maximum == 12
    assert point.count == 4


def test_azure_monitor_normalizes_dashboard_metrics():
    summary = _normalize_metrics(
        [
            MonitorMetricPoint(name="GeneratedTokens", total=250),
            MonitorMetricPoint(name="Requests", total=4),
            MonitorMetricPoint(name="Latency", average=320),
            MonitorMetricPoint(name="FailedRequests", total=1),
            MonitorMetricPoint(name="ThrottledRequests", total=2),
        ],
        token_limit=1000,
    )

    assert summary["tokens_used"] == 250
    assert summary["request_count"] == 4
    assert summary["latency_ms"] == 320
    assert summary["error_count"] == 1
    assert summary["throttled_count"] == 2
    assert summary["model_load_percent"] == 25
