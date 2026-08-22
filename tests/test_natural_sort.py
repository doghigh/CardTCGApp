# tests/test_natural_sort.py
"""Regression: plain sorted(Path) scrambles numerically-named batches.

Both ui/batch_tab.py's folder import and core/watcher.py's watch-folder
import glob a directory and sort the results with no key — a plain string
sort, which orders 'IMG_10.jpg' before 'IMG_2.jpg' because '1' < '2'
lexicographically. At real batch sizes (a user reported this at 243 files)
that scrambles almost the entire scan order once file numbers cross a
digit-count boundary.
"""
from pathlib import Path

from utils.natural_sort import natural_sort_key


def test_orders_embedded_numbers_by_value_not_lexicographically():
    names = ["IMG_1.jpg", "IMG_2.jpg", "IMG_9.jpg", "IMG_10.jpg", "IMG_100.jpg"]
    assert sorted(names, key=natural_sort_key) == names


def test_matches_plain_sort_for_zero_padded_names():
    """Zero-padded names already sort correctly either way — must not regress."""
    names = ["scan_001.jpg", "scan_002.jpg", "scan_010.jpg", "scan_100.jpg"]
    assert sorted(names, key=natural_sort_key) == names


def test_reproduces_and_fixes_the_243_file_scramble():
    """The exact scenario from the field report, scaled down to 12 files."""
    scan_order = [f"IMG_{i}.jpg" for i in range(1, 13)]
    shuffled = sorted(scan_order)  # the OLD behavior — plain string sort
    assert shuffled != scan_order, "test setup should reproduce the scramble"

    fixed = sorted(scan_order, key=natural_sort_key)
    assert fixed == scan_order


def test_works_on_path_objects_not_just_strings(tmp_path):
    for name in ["card_9.png", "card_10.png", "card_2.png"]:
        (tmp_path / name).touch()
    files = sorted(tmp_path.glob("*.png"), key=natural_sort_key)
    assert [f.name for f in files] == ["card_2.png", "card_9.png", "card_10.png"]


def test_multiple_number_runs_in_one_name():
    names = ["set2_card10.jpg", "set2_card9.jpg", "set10_card1.jpg"]
    assert sorted(names, key=natural_sort_key) == [
        "set2_card9.jpg", "set2_card10.jpg", "set10_card1.jpg"
    ]


def test_case_insensitive_like_windows_filesystems():
    names = ["Img_2.jpg", "img_10.jpg", "IMG_1.jpg"]
    assert sorted(names, key=natural_sort_key) == ["IMG_1.jpg", "Img_2.jpg", "img_10.jpg"]
