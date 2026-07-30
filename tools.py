"""The three functions the model may call, and the schemas it sees for them.

Two things live in this file on purpose:

  * the Python implementations, which read expenses.csv and return plain dicts;
  * the JSON Schemas passed as `tools=[...]`, which are the only thing the model
    knows about them. The `description` strings are therefore part of the program's
    behaviour: vague wording here shows up as wrong arguments at runtime.

Nothing here talks to the network. `call_tool` is the single entry point the loop
in agent.py uses, and it always returns a JSON string, including for failures.
"""

import csv
import json
from pathlib import Path

DATA = Path(__file__).with_name("expenses.csv")


def _rows():
    with DATA.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            row["amount_usd"] = float(row["amount_usd"])
            yield row


def list_categories():
    """Every category present in the file, with how many rows each has."""
    counts = {}
    for row in _rows():
        counts[row["category"]] = counts.get(row["category"], 0) + 1
    return {"categories": [{"category": c, "rows": n} for c, n in sorted(counts.items())]}


def sum_expenses(category=None, since=None, until=None):
    """Total spend, optionally narrowed by category and an ISO date window."""
    matched = []
    for row in _rows():
        if category and row["category"] != category:
            continue
        if since and row["date"] < since:
            continue
        if until and row["date"] > until:
            continue
        matched.append(row)
    return {
        "total_usd": round(sum(r["amount_usd"] for r in matched), 2),
        "rows": len(matched),
        "filter": {"category": category, "since": since, "until": until},
    }


def top_vendors(limit=3):
    """The vendors we paid the most, biggest first."""
    totals = {}
    for row in _rows():
        totals[row["vendor"]] = totals.get(row["vendor"], 0.0) + row["amount_usd"]
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    return {"vendors": [{"vendor": v, "total_usd": round(t, 2)} for v, t in ranked[:limit]]}


# What the model receives. Each entry mirrors one function above; the parameter
# names must match the Python keyword arguments, because that is how the loop
# calls them (`fn(**json.loads(arguments))`).
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_categories",
            "description": "List the expense categories that exist in the ledger, with row counts. "
                           "Call this first if you are unsure which category names are valid.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sum_expenses",
            "description": "Sum spend in USD. Leave every argument out for the all-time total.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Exact category name, e.g. cloud. Omit for all categories.",
                    },
                    "since": {"type": "string", "description": "Inclusive start date, YYYY-MM-DD."},
                    "until": {"type": "string", "description": "Inclusive end date, YYYY-MM-DD."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "top_vendors",
            "description": "Rank vendors by total spend, highest first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "How many vendors to return (default 3)."},
                },
            },
        },
    },
]

IMPLS = {
    "list_categories": list_categories,
    "sum_expenses": sum_expenses,
    "top_vendors": top_vendors,
}


def call_tool(name, arguments):
    """Run one requested call. `arguments` arrives as a JSON *string*, never a dict.

    Errors are returned as JSON rather than raised: the model can read the message
    on the next turn and retry with better arguments, which is usually what you want
    from a typo in a category name.
    """
    fn = IMPLS.get(name)
    if fn is None:
        return json.dumps({"error": "no such tool: %s" % name, "available": sorted(IMPLS)})
    try:
        kwargs = json.loads(arguments or "{}")
    except json.JSONDecodeError as exc:
        return json.dumps({"error": "arguments were not valid JSON: %s" % exc})
    try:
        return json.dumps(fn(**kwargs))
    except TypeError as exc:
        return json.dumps({"error": "bad arguments for %s: %s" % (name, exc)})
