"""This month's Azure cost for the project, from the Azure Cost Management API.

The website reads it with its managed identity, which Terraform gives the "Cost Management Reader"
role on the resource group. Results are cached for an hour: cost data only updates a few times a
day, and the API allows a limited number of calls.

  AZURE_COST_SCOPE   the resource group to report on, e.g. /subscriptions/<id>/resourceGroups/imagevault-rg
  MONTHLY_BUDGET     the budget shown next to the cost (set by Terraform from var.monthly_budget)
"""

import json
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from app.config import env, running_on_azure

CACHE_SECONDS = 3600
ERROR_CACHE_SECONDS = 600
API_VERSION = "2023-11-01"

_cache: dict = {}
_lock = threading.Lock()


def _query(scope: str) -> dict:
    from azure.identity import DefaultAzureCredential

    credential = DefaultAzureCredential(exclude_managed_identity_credential=not running_on_azure())
    token = credential.get_token("https://management.azure.com/.default").token
    body = {
        "type": "ActualCost",
        "timeframe": "MonthToDate",
        "dataset": {
            "granularity": "None",
            "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
            "grouping": [{"type": "Dimension", "name": "ServiceName"}],
        },
    }
    request = urllib.request.Request(
        f"https://management.azure.com{scope}/providers/Microsoft.CostManagement/query?api-version={API_VERSION}",
        data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)["properties"]
    columns = [c["name"] for c in result["columns"]]
    services, currency = [], "USD"
    for row in result["rows"]:
        values = dict(zip(columns, row))
        currency = values.get("Currency", currency)
        services.append({"name": values.get("ServiceName") or "Other", "amount": round(float(values["Cost"]), 4)})
    services.sort(key=lambda s: s["amount"], reverse=True)
    return {"amount": round(sum(s["amount"] for s in services), 2), "currency": currency, "services": services}


def month_to_date() -> dict:
    """{"configured", "amount", "currency", "budget", "services", "updated_at", "error"}"""
    scope = env("AZURE_COST_SCOPE")
    budget = float(env("MONTHLY_BUDGET", "0") or 0) or None
    if not scope:
        return {"configured": False, "budget": budget}
    with _lock:
        cached = _cache.get(scope)
        if cached and time.monotonic() < cached["expires"]:
            return cached["value"]
    try:
        value = {"configured": True, "budget": budget, "error": None, **_query(scope)}
        lifetime = CACHE_SECONDS
    except Exception as exc:  # cost data is nice to have; never break the page
        if cached and cached["value"].get("error") is None:
            value = cached["value"]  # keep showing the last good numbers
        elif isinstance(exc, urllib.error.HTTPError) and exc.code == 429:
            value = {"configured": True, "budget": budget,
                     "error": "Azure's cost service is busy right now (it limits how often costs can be read). "
                              "This card refreshes by itself in a few minutes."}
        else:
            message = str(exc).splitlines()[0][:200]
            value = {"configured": True, "budget": budget, "error": f"Could not read costs: {message}"}
        lifetime = ERROR_CACHE_SECONDS
    value["updated_at"] = datetime.now(timezone.utc).isoformat()
    with _lock:
        _cache[scope] = {"value": value, "expires": time.monotonic() + lifetime}
    return value
