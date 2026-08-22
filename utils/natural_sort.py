"""Natural (numeric-aware) sort key for filenames.

Plain string sorting orders 'IMG_10.jpg' before 'IMG_2.jpg' — '1' < '2' as
characters — which scrambles any batch of sequentially-numbered files once
the file count crosses a digit boundary. This key splits each name into
alternating text/number runs and compares number runs by value.
"""
import re

_RUN_RE = re.compile(r'(\d+)')


def natural_sort_key(path) -> list:
    """Sort key: 'card_9.png' < 'card_10.png', case-insensitive on the text runs."""
    s = str(path)
    return [int(run) if run.isdigit() else run.lower()
            for run in _RUN_RE.split(s)]
