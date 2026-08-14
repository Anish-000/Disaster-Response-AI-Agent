"""
ai_summary.py
Optional Gemini-based summarizer for the action plan. Isolated on purpose:
if this breaks (bad key, quota, network), it must never crash the main app —
it just returns None and the UI falls back to the local heuristic plan.

Fix vs. the original code: the old version called
    genai_client.GenerativeModel(api_key=...).generate(prompt=..., model=...)
which doesn't exist in the current google-genai SDK. The correct pattern is:
    client = genai.Client(api_key=...)
    client.models.generate_content(model=..., contents=...)
"""

from config import GEMINI_MODEL

try:
    from google import genai
    _GENAI_AVAILABLE = True
except Exception:
    _GENAI_AVAILABLE = False


def summarize_action_plan(action_plan: list, api_key: str) -> str | None:
    """
    Sends the action plan lines to Gemini and asks for a 1-line summary + 4 bullets.
    Returns None (never raises) if the key is missing, the SDK isn't installed,
    or the API call fails for any reason — caller should fall back to the raw plan.
    """
    if not api_key or not _GENAI_AVAILABLE:
        return None
    if not action_plan:
        return None

    try:
        client = genai.Client(api_key=api_key)
        prompt = (
            "Summarize the following disaster action plan into a 1-line headline "
            "and 4 short bullet points a non-expert can follow quickly:\n\n"
            + "\n".join(action_plan)
        )
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        return getattr(response, "text", None)
    except Exception:
        # Network error, bad key, quota exceeded, etc. — fail silently and
        # let the caller show the local heuristic plan instead.
        return None