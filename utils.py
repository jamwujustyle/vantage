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
