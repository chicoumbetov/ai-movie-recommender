import json
import time

PRICE = {"gpt-6-luna": (0.10, 0.50), "gpt-6-astra": (10.00, 50.00), "qwen3.5:4b": (0.00, 0.00)}


def log(model, request, outcome, started, completion=None):
    row = {
        "time": time.strftime("%H:%M:%S"),
        "model": model,
        "request": request,
        "outcome": outcome,
        "seconds": round(time.time() - started, 1),
    }
    if completion:
        usage = completion.usage
        price_in, price_out = PRICE.get(model, (0, 0))
        row["id"] = completion.id
        row["usage"] = usage.model_dump()
        row["usd"] = (
            usage.prompt_tokens * price_in + usage.completion_tokens * price_out
        ) / 1_000_000
    with open("calls.jsonl", "a", encoding="utf-8") as file:
        file.write(json.dumps(row, ensure_ascii=False) + "\n")
