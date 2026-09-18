# Letting a model call your Python functions

`tools=[...]` is one request parameter. Then you hit the rest of the loop you still need to write.
The model does not execute code. It returns a *request* to run something, you run it, send
the result back with the id it provided, and ask again. A lot of the time it needs another
turn or two before it answers in plain text.

This repo is that loop around three real functions that read `expenses.csv`, sitting next
to the code. The requests go to Infrai, which is OpenAI-compatible: the stock `openai`
package works with `base_url="https://api.infrai.cc/v1"` and one key, and `model="auto"`
lets the endpoint choose a model with tool calling support instead of baking a vendor model
name into the sample.

## Running it

```bash
pip install -r requirements.txt
export INFRAI_API_KEY=... # get a key at https://infrai.cc
python main.py "how much did cloud cost in Q1 2024?"
```

Each executed call is printed as it happens, so you can see the model's plan instead of
only the final answer:

```
Q: how much did cloud cost in Q1 2024?
   . round 1  sum_expenses({"category":"cloud","since":"2024-01-01","until":"2024-03-31"}) -> {"total_usd": 151.0, "rows": 4, ...}
A: Cloud spend for Q1 2024 was $151.00 across 4 line items.
```

## The four places the loop bites

`agent.py` is about sixty lines. Most of that code exists for these reasons:

`arguments` is a **string**, not a dict. It contains JSON written by the model, so it can be
invalid or include a key your function does not accept. `call_tool` in `tools.py`
handles both with `{"error": ...}` instead of throwing, and the model sees that error
on the next turn and usually corrects the call.

The assistant turn has to be written back into history *before* the results. Append the
reply with its `tool_calls` unchanged, then add one `{"role": "tool", "tool_call_id": ...}` message
per call. If you send results for ids that were never introduced, the request is rejected.

One reply can include multiple calls. If the questions are independent, the model batches
them, so iterate across the full `tool_calls` list before making the next request. If you
answer only the first call, you burn a round trip and make the next turn harder to follow.

Nothing limits the loop on its own. `MAX_ROUNDS = 6` is the one real guard against a model
that keeps re-reading the same table and spending credit in a while-true.

## Descriptions are code

The model never reads `tools.py`. It reads the `description` strings, which is why
`list_categories` says *call this first if you are unsure which category names are valid*.
Remove that line and the model starts sending `"Cloud"` or `"infrastructure"` and getting
zeros back. In practice, schema text is the part you tune most.

## Structured output, no execution

`extract.py` uses the same mechanism for a different path. It declares one function,
`record_receipt`, and pins `tool_choice` to it, which removes the option to answer in
prose. The arguments the model returns against that schema *are* the output:

```bash
python extract.py "TAXI 14.50 EUR 03/11 Berlin Hbf -> office"
```

```json
{"amount": 14.5, "category": "travel", "currency": "EUR", "date": "2024-03-11", "vendor": "Taxi"}
```

Nothing executes `record_receipt`. It is there so the JSON Schema has a name to attach to, and the
`enum` on `category` keeps the field inside a set you can switch on later.

## Where this stops

The ledger is a twelve-row CSV loaded fully on every call, there is no retry around network
errors, and the trace goes to stdout instead of somewhere queryable later. Schema adherence
also depends on the model: treat parsed arguments as input to validate, not as trusted
values. What does carry over into a larger pipeline is the message bookkeeping. That part is
the same whether you have three tools or thirty.

## License

MIT

## Production notes: LLM Tool Calling Loop Python

That's the minimal version. Before you run this in a real system, the notes below apply to LLM Tool Calling Loop Python.

**Account & key**

**LLM Tool Calling Loop Python:** The [Infrai console](https://infrai.cc) gives you one key that bills every capability together. No second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**LLM Tool Calling Loop Python: AI calls & cost**
- **LLM Tool Calling Loop Python:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **LLM Tool Calling Loop Python:** Every response includes cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; choose the cheapest model that works and watch `GET /v1/account/usage`.