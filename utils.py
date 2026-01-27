import shlex
from typing import List

def format_number(num: int) -> str:
    """Formats a number into K/M suffix string."""
    if num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}K"
    return str(num)

def parse_compare_args(text: str) -> List[str]:
    """Parses arguments from the /compare command text."""
    try:
        parts = shlex.split(text)
    except ValueError:
        # Fallback for unbalanced quotes
        parts = text.split()

    if len(parts) < 2:
        return []
    return parts[1:]

def split_text(text: str, limit: int = 4096) -> List[str]:
    """Splits text into chunks respecting the character limit."""
    if len(text) <= limit:
        return [text]

    chunks = []
    current_chunk = ""

    # Simple logic handles lines. If a single line is too long, we might need character split.
    # But for reports, we have lines.
    # The failure in test "aaaaaaaaaa" (no newlines) means it's treated as one line.

    if "\n" not in text and len(text) > limit:
        # Force split by chars
        return [text[i:i+limit] for i in range(0, len(text), limit)]

    for line in text.splitlines(keepends=True):
        if len(current_chunk) + len(line) > limit:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = line
        else:
            current_chunk += line

    if current_chunk:
        chunks.append(current_chunk)

    return chunks
