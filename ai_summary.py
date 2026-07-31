# ai_summary.py
#
# The AI feature: turn a raw fault record into a short, operator-facing
# natural-language summary. This is deliberately the ONLY place an LLM
# touches this system - it does not participate in localization (that stays
# deterministic, per the assignment's explicit warning).
#
# Why here: the fault-detection output ({"span": "P-2 -> P-3", "downstream_
# affected": 4, "confidence": "high"}) is precise but not how a tired 2am
# operator wants to read an alert. Turning structured data into one plain
# sentence is exactly what LLMs are good at, it's low-stakes if occasionally
# imperfect (the structured data is still shown alongside it, not replaced),
# and it degrades safely - see the fallback below.

import os
import json
import urllib.request
import urllib.error

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-5-20250929"


def _fallback_summary(fault):
    """Deterministic, templated summary - used when the API key is missing,
    the call fails, or the model times out. The operator always gets a
    usable message, never a broken UI."""
    confidence_note = (
        "" if fault["confidence"] == "high"
        else " (location is approximate - based on inferred wiring, not surveyed data)"
    )
    return (
        f"Fault on span {fault['span']}. "
        f"{fault['downstream_affected']} pole(s) currently without power{confidence_note}."
    )


def generate_fault_summary(fault):
    """
    fault: {"span": str, "downstream_affected": int, "confidence": str}
    Returns a one-sentence natural language summary for the operator console.
    Never raises - falls back to a template on any failure.
    """
    if not ANTHROPIC_API_KEY:
        return _fallback_summary(fault)

    prompt = (
        "You are writing a one-sentence alert for a power grid control room "
        "operator. Be plain, direct, and calm - no exclamation marks, no "
        "hype. State what broke, how many homes are affected, and if "
        "confidence is not 'high', mention the location is approximate.\n\n"
        f"Fault data: {json.dumps(fault)}\n\n"
        "Respond with ONLY the one sentence, nothing else."
    )

    body = json.dumps({
        "model": MODEL,
        "max_tokens": 100,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return data["content"][0]["text"].strip()
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, TimeoutError, Exception):
        # Any failure (bad key, network issue, rate limit, unexpected
        # response shape) - fall back rather than break the console.
        return _fallback_summary(fault)


if __name__ == "__main__":
    test_fault = {"span": "P-2 -> P-3", "downstream_affected": 4, "confidence": "high"}
    print("No API key set, so this will use the fallback:")
    print(generate_fault_summary(test_fault))
