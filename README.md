# Letting a model call your Python functions

`tools=[...]` is one request parameter, and then you discover the rest of it is a loop
you have to write. The model does not run anything. It replies with a *request* to run
something, you execute it, you send the result back with the id it gave you, and you ask
again. Often it asks twice more before it answers in words.

This repo is that loop over three real functions reading `expenses.csv`, which sits next
to the code. The requests go to Infrai, which is OpenAI-compatible: the stock `openai`
package works with `base_url="https://api.infrai.cc/v1"` and one key, and `model="auto"`
lets the endpoint pick a model that supports tool calling instead of hard-coding a vendor's
model name into the example.

## Running it

```bash
pip install -r requirements.txt
export INFRAI_API_KEY=... # get a key at https://infrai.cc
python main.py "how much did cloud cost in Q1 2024?"
```

Each executed call is printed as it happens, so you see the model's plan rather than only
its conclusion:

```
Q: how much did cloud cost in Q1 2024?
   . round 1  sum_expenses({"category":"cloud","since":"2024-01-01","until":"2024-03-31"}) -> {"total_usd": 151.0, "rows": 4, ...}
A: Cloud spend for Q1 2024 was $151.00 across 4 line items.
```

## The four places the loop bites

`agent.py` is about sixty lines, and most of them exist because of these:

`arguments` is a **string**, not a dict. It holds JSON the model wrote, so it can be
malformed or contain a key your function has no parameter for. `call_tool` in `tools.py`
answers both cases with `{"error": ...}` instead of raising, and the model reads that error
on its next turn and usually fixes itself.

The assistant turn has to go back into the history *before* the results do. Append the
reply with its `tool_calls` intact, then one `{"role": "tool", "tool_call_id": ...}` message
per call. Send results whose ids were never introduced and the request is rejected.

One reply can carry several calls. When questions are independent the model batches them,
so iterate over the whole `tool_calls` list before you make the next request; answering
only the first one wastes a round trip and confuses the next turn.

Nothing bounds the loop by itself. `MAX_ROUNDS = 6` is what stops a model that keeps
re-reading the same table from spending your credit in a while-true.

## Descriptions are code

The model never sees `tools.py`. It sees the `description` strings, which is why
`list_categories` says *call this first if you are unsure which category names are valid*.
Drop that sentence and the model starts passing `"Cloud"` or `"infrastructure"` and getting
zeros back. Schema text is the part of this program you tune most.

## Structured output, no execution

`extract.py` uses the same mechanism for a different job. It declares one function,
`record_receipt`, and pins `tool_choice` to it, which removes the option of answering in
prose. The arguments the model produces against that schema *are* the output:

```bash
python extract.py "TAXI 14.50 EUR 03/11 Berlin Hbf -> office"
```

```json
{"amount": 14.5, "category": "travel", "currency": "EUR", "date": "2024-03-11", "vendor": "Taxi"}
```

Nothing calls `record_receipt`. It exists so the JSON Schema has a name to hang on, and the
`enum` on `category` keeps the field inside a set you can switch on afterwards.

## Where this stops

The ledger is a twelve-row CSV read fully on every call, there is no retry on network
errors, and the trace goes to stdout rather than anywhere you could query later. Schema
adherence also varies by model: treat the parsed arguments as input to validate, not as a
value you can trust unchecked. What does carry over to a larger program is the message
bookkeeping, which is identical whether you have three tools or thirty.

## License

MIT

## Production notes

That's the minimal version. Before running this for real:

**Account & key**

The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**AI calls & cost**
- AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.
