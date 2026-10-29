"""Provider availability is informational; incorrect itinerary content is blocking."""

import re


def apply_review_policy(review):
    blocking, notes = [], list(review.get("notes", []))
    removed = False
    for issue in review["issues"]:
        text = issue["problem"].casefold()
        missing = re.search(
            r"\b(missing|unavailable|failed|no pricing|no prices|not retrieved|not confirmed|cannot verify)\b",
            text,
        )
        provider = re.search(
            r"\b(cost|costs|price|prices|pricing|quote|quotes|accommodation|hotel|weather|opening hours|availability)\b",
            text,
        )
        incorrect = re.search(
            r"\b(invented|fabricated|wrong|incorrect|mismatch|exceeds|exceed|unsafe|unrelated|invalid|unsupported|unsourced)\b",
            text,
        )
        if missing and provider and not incorrect:
            notes.append(issue["problem"])
            removed = True
        else:
            blocking.append(issue)
    return {
        **review,
        "issues": blocking,
        "notes": list(dict.fromkeys(notes)),
        "status": "APPROVED"
        if removed and not blocking
        else ("NEEDS_REVISION" if blocking else review["status"]),
    }
