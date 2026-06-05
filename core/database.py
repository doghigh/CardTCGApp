"""
Database module for Trading Card Manager.
Fixed: SQL Injection prevention, better error handling, input validation.
"""

import sqlite3
import json
import threading
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime


class Database:
    """Thread-safe SQLite database handler."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _conn(self):
        """Create a new database connection."""
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self):
        """Initialize database schema."""
        with self._lock, self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS cards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    set_name TEXT,
                    card_number TEXT,
                    rarity TEXT,
                    game TEXT,
                    year INTEGER,
                    language TEXT DEFAULT 'English',
                    foil INTEGER DEFAULT 0,
                    front_scan_path TEXT,
                    back_scan_path TEXT,
                    condition_grade TEXT,
                    condition_score REAL,
                    defects_json TEXT,
                    estimated_value REAL DEFAULT 0,
                    purchase_price REAL DEFAULT 0,
                    purchase_date TEXT,
                    notes TEXT,
                    quantity INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS valuations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    card_id INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    value REAL NOT NULL,
                    currency TEXT DEFAULT 'USD',
                    url TEXT,
                    fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    period_start TEXT NOT NULL,
                    period_end TEXT NOT NULL,
                    total_cards INTEGER,
                    total_value REAL,
                    file_path TEXT,
                    generated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_cards_name ON cards(name);
                CREATE INDEX IF NOT EXISTS idx_cards_set ON cards(set_name);
                CREATE INDEX IF NOT EXISTS idx_cards_game ON cards(game);
                CREATE INDEX IF NOT EXISTS idx_valuations_card ON valuations(card_id);
            """)

    # ── Input validation ─────────────────────────────────────────────────────

    def _validate_card(self, card: Dict) -> Dict:
        """Sanitise and type-check all card fields before writing to the DB."""
        v = dict(card)
        current_year = datetime.now().year

        # name — required, max 200 chars
        name = str(v.get('name') or '').strip()[:200]
        v['name'] = name or 'Unknown'

        # year — 1800 … current+1 or None
        year = v.get('year')
        if year is not None:
            try:
                year = int(year)
                year = year if 1800 <= year <= current_year + 1 else None
            except (ValueError, TypeError):
                year = None
        v['year'] = year

        # quantity — 1 … 9 999
        try:
            v['quantity'] = max(1, min(9_999, int(v.get('quantity', 1))))
        except (ValueError, TypeError):
            v['quantity'] = 1

        # prices — non-negative, max $1 000 000
        for field in ('purchase_price', 'estimated_value'):
            try:
                val = float(v.get(field) or 0.0)
                v[field] = round(max(0.0, min(1_000_000.0, val)), 2)
            except (ValueError, TypeError):
                v[field] = 0.0

        # condition_score — 0 … 100
        score = v.get('condition_score')
        if score is not None:
            try:
                v['condition_score'] = round(max(0.0, min(100.0, float(score))), 1)
            except (ValueError, TypeError):
                v['condition_score'] = None

        # foil — strict boolean
        v['foil'] = 1 if v.get('foil') else 0

        # bounded text fields
        _limits = {
            'set_name': 200, 'card_number': 50, 'rarity': 50,
            'game': 100, 'language': 50, 'condition_grade': 50,
        }
        for field, max_len in _limits.items():
            val = v.get(field)
            if val is not None:
                cleaned = str(val).strip()[:max_len]
                v[field] = cleaned if cleaned else None

        # notes — up to 2 000 chars
        notes = v.get('notes')
        if notes:
            v['notes'] = str(notes).strip()[:2_000]

        return v

    def find_duplicate(self, card: Dict) -> Optional[int]:
        """
        Return the id of an existing card that is the same printing, or None.

        Match key: name (case-insensitive) + set + card number + game + foil.
        Condition is intentionally excluded so multiple copies of the same card
        combine into one quantity even if the grader scored them slightly
        differently.
        """
        with self._lock, self._conn() as conn:
            row = conn.execute("""
                SELECT id FROM cards
                WHERE LOWER(IFNULL(name,'')) = LOWER(IFNULL(?,''))
                  AND IFNULL(set_name,'')    = IFNULL(?,'')
                  AND IFNULL(card_number,'') = IFNULL(?,'')
                  AND IFNULL(game,'')        = IFNULL(?,'')
                  AND IFNULL(foil,0)         = IFNULL(?,0)
                ORDER BY id ASC LIMIT 1
            """, (
                card.get('name'), card.get('set_name'),
                card.get('card_number'), card.get('game'),
                int(card.get('foil', 0)),
            )).fetchone()
            return int(row['id']) if row else None

    def add_card(self, card: Dict, merge_duplicates: bool = True) -> int:
        """
        Add a card after validation.

        If merge_duplicates is True (default) and a matching card already
        exists, its quantity is increased instead of inserting a new row;
        the existing card's id is returned.
        """
        card = self._validate_card(card)

        if merge_duplicates:
            dup_id = self.find_duplicate(card)
            if dup_id is not None:
                add_qty = int(card.get('quantity', 1) or 1)
                with self._lock, self._conn() as conn:
                    conn.execute(
                        "UPDATE cards SET quantity = quantity + ?, "
                        "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (add_qty, dup_id),
                    )
                return dup_id

        with self._lock, self._conn() as conn:
            cursor = conn.execute("""
                INSERT INTO cards (
                    name, set_name, card_number, rarity, game, year, language, foil,
                    front_scan_path, back_scan_path, condition_grade, condition_score,
                    defects_json, estimated_value, purchase_price, purchase_date, notes, quantity
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                card.get('name', 'Unknown'),
                card.get('set_name'),
                card.get('card_number'),
                card.get('rarity'),
                card.get('game'),
                card.get('year'),
                card.get('language', 'English'),
                int(card.get('foil', 0)),
                card.get('front_scan_path'),
                card.get('back_scan_path'),
                card.get('condition_grade'),
                card.get('condition_score'),
                json.dumps(card.get('defects', [])),
                card.get('estimated_value', 0.0),
                card.get('purchase_price', 0.0),
                card.get('purchase_date'),
                card.get('notes'),
                card.get('quantity', 1)
            ))
            return cursor.lastrowid

    def merge_existing_duplicates(self) -> Dict[str, int]:
        """
        Consolidate duplicate rows already in the collection.

        Groups by name (case-insensitive) + set + card number + game + foil.
        For each group of 2+, keeps the earliest (lowest id), sums quantities
        into it, adopts a scan image if the keeper lacks one, deletes the rest,
        and removes their now-orphaned scan files.

        Returns {'groups': merged_group_count, 'removed': deleted_row_count}.
        """
        delete_paths: List[str] = []
        merged_groups = 0
        removed = 0

        with self._lock, self._conn() as conn:
            rows = conn.execute("SELECT * FROM cards ORDER BY id ASC").fetchall()
            groups: Dict[tuple, List] = {}
            for r in rows:
                key = (
                    (r['name'] or '').strip().lower(),
                    (r['set_name'] or '').strip(),
                    (r['card_number'] or '').strip(),
                    (r['game'] or '').strip(),
                    int(r['foil'] or 0),
                )
                groups.setdefault(key, []).append(r)

            for members in groups.values():
                if len(members) < 2:
                    continue
                keeper = members[0]
                keep_front = keeper['front_scan_path']
                keep_back = keeper['back_scan_path']
                new_qty = int(keeper['quantity'] or 1)

                for m in members[1:]:
                    new_qty += int(m['quantity'] or 1)
                    # Adopt an image only if the keeper is missing one
                    if not keep_front and m['front_scan_path']:
                        keep_front = m['front_scan_path']
                    elif m['front_scan_path']:
                        delete_paths.append(m['front_scan_path'])
                    if not keep_back and m['back_scan_path']:
                        keep_back = m['back_scan_path']
                    elif m['back_scan_path']:
                        delete_paths.append(m['back_scan_path'])
                    conn.execute("DELETE FROM cards WHERE id = ?", (m['id'],))
                    removed += 1

                conn.execute(
                    "UPDATE cards SET quantity = ?, front_scan_path = ?, "
                    "back_scan_path = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (new_qty, keep_front, keep_back, keeper['id']),
                )
                merged_groups += 1

        # Remove orphaned scan files outside the DB lock
        for path in delete_paths:
            try:
                Path(path).unlink(missing_ok=True)
            except OSError:
                pass

        return {'groups': merged_groups, 'removed': removed}

    def update_card(self, card_id: int, updates: Dict):
        """Safe update: column whitelist + type validation."""
        allowed_fields = {
            'name', 'set_name', 'card_number', 'rarity', 'game', 'year',
            'language', 'foil', 'condition_grade', 'condition_score',
            'estimated_value', 'purchase_price', 'purchase_date', 'notes',
            'quantity', 'defects',
        }

        # Only touch the fields the caller actually provided. _validate_card
        # injects defaults (foil=0, quantity=1, year=None, …); writing those
        # for an un-passed field would clobber existing data, so we validate
        # then emit columns strictly limited to the provided keys.
        provided = {k for k in updates if k in allowed_fields}
        if not provided:
            return
        validated = self._validate_card({**updates, 'name': updates.get('name', '')})

        fields = []
        values = []
        for k in provided:
            v = validated.get(k)
            if k == 'defects':
                fields.append("defects_json = ?")
                values.append(json.dumps(v))
            else:
                fields.append(f"{k} = ?")
                values.append(v)

        if not fields:
            return

        fields.append("updated_at = CURRENT_TIMESTAMP")
        values.append(card_id)

        query = f"UPDATE cards SET {', '.join(fields)} WHERE id = ?"
        with self._lock, self._conn() as conn:
            conn.execute(query, values)

    def delete_card(self, card_id: int):
        """Delete a card by ID."""
        with self._lock, self._conn() as conn:
            conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))

    def get_card(self, card_id: int) -> Optional[Dict]:
        with self._lock, self._conn() as conn:
            row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
            return dict(row) if row else None

    def get_all_cards(self, search: str = None) -> List[Dict]:
        with self._lock, self._conn() as conn:
            # Tiebreak on id (ascending) so cards saved in the same second —
            # e.g. a 30-card batch — keep their scan/insertion order instead of
            # appearing scrambled (CURRENT_TIMESTAMP only has 1-second resolution).
            if search and search.strip():
                term = f"%{search.strip()}%"
                rows = conn.execute("""
                    SELECT * FROM cards
                    WHERE name LIKE ? OR set_name LIKE ? OR game LIKE ? OR card_number LIKE ?
                    ORDER BY updated_at DESC, id ASC
                """, (term, term, term, term)).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM cards ORDER BY updated_at DESC, id ASC"
                ).fetchall()
            return [dict(r) for r in rows]

    def add_valuation(self, card_id: int, source: str, value: float, url: Optional[str] = None):
        with self._lock, self._conn() as conn:
            conn.execute("""
                INSERT INTO valuations (card_id, source, value, url)
                VALUES (?, ?, ?, ?)
            """, (card_id, source, value, url))

    def get_valuations(self, card_id: int) -> List[Dict]:
        with self._lock, self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM valuations WHERE card_id = ? ORDER BY fetched_at DESC
            """, (card_id,)).fetchall()
            return [dict(r) for r in rows]

    def get_collection_stats(self) -> Dict:
        with self._lock, self._conn() as conn:
            row = conn.execute("""
                SELECT 
                    COUNT(*) as total_cards,
                    COALESCE(SUM(quantity), 0) as total_quantity,
                    COALESCE(SUM(estimated_value * quantity), 0) as total_value,
                    COALESCE(SUM(purchase_price * quantity), 0) as total_cost,
                    COALESCE(AVG(condition_score), 0) as avg_condition
                FROM cards
            """).fetchone()
            return dict(row) if row else {}

    def get_cards_for_period(self, start: str, end: str) -> List[Dict]:
        with self._lock, self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM cards 
                WHERE created_at BETWEEN ? AND ?
                ORDER BY estimated_value DESC
            """, (start, end)).fetchall()
            return [dict(r) for r in rows]

    def save_report(self, period_start: str, period_end: str, total_cards: int,
                    total_value: float, file_path: str) -> int:
        with self._lock, self._conn() as conn:
            cursor = conn.execute("""
                INSERT INTO reports (period_start, period_end, total_cards, total_value, file_path)
                VALUES (?, ?, ?, ?, ?)
            """, (period_start, period_end, total_cards, total_value, file_path))
            return cursor.lastrowid

    def get_reports(self) -> List[Dict]:
        with self._lock, self._conn() as conn:
            rows = conn.execute("SELECT * FROM reports ORDER BY generated_at DESC").fetchall()
            return [dict(r) for r in rows]