import sqlite3
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict


class Database:
    """Handles all database operations with thread safety."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _conn(self):
        """Create a new connection with row factory."""
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self):
        """Create tables and indexes if they don't exist."""
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

    def add_card(self, card: Dict) -> int:
        """Add a new card and return its ID."""
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

    def update_card(self, card_id: int, updates: Dict):
        """Update an existing card."""
        with self._lock, self._conn() as conn:
            fields = []
            values = []
            for k, v in updates.items():
                if k == 'defects':
                    fields.append("defects_json = ?")
                    values.append(json.dumps(v))
                else:
                    fields.append(f"{k} = ?")
                    values.append(v)
            fields.append("updated_at = CURRENT_TIMESTAMP")
            values.append(card_id)

            conn.execute(f"UPDATE cards SET {', '.join(fields)} WHERE id = ?", values)

    def delete_card(self, card_id: int):
        """Delete a card."""
        with self._lock, self._conn() as conn:
            conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))

    def get_card(self, card_id: int) -> Optional[Dict]:
        """Get single card by ID."""
        with self._lock, self._conn() as conn:
            row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
            return dict(row) if row else None

    def get_all_cards(self, search: str = None) -> List[Dict]:
        """Get all cards, optionally filtered by search term."""
        with self._lock, self._conn() as conn:
            if search:
                query = """
                    SELECT * FROM cards 
                    WHERE name LIKE ? OR set_name LIKE ? OR game LIKE ? OR card_number LIKE ?
                    ORDER BY updated_at DESC
                """
                rows = conn.execute(query, (f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%")).fetchall()
            else:
                rows = conn.execute("SELECT * FROM cards ORDER BY updated_at DESC").fetchall()
            return [dict(r) for r in rows]

    def add_valuation(self, card_id: int, source: str, value: float, url: str = None):
        """Add a valuation record."""
        with self._lock, self._conn() as conn:
            conn.execute("""
                INSERT INTO valuations (card_id, source, value, url)
                VALUES (?, ?, ?, ?)
            """, (card_id, source, value, url))

    def get_valuations(self, card_id: int) -> List[Dict]:
        """Get all valuations for a card."""
        with self._lock, self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM valuations 
                WHERE card_id = ? 
                ORDER BY fetched_at DESC
            """, (card_id,)).fetchall()
            return [dict(r) for r in rows]

    def get_collection_stats(self) -> Dict:
        """Return overall collection statistics."""
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
        """Get cards added in a specific date range."""
        with self._lock, self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM cards 
                WHERE created_at BETWEEN ? AND ?
                ORDER BY estimated_value DESC
            """, (start, end)).fetchall()
            return [dict(r) for r in rows]

    def save_report(self, period_start: str, period_end: str, total_cards: int,
                    total_value: float, file_path: str) -> int:
        """Save a generated report record."""
        with self._lock, self._conn() as conn:
            cursor = conn.execute("""
                INSERT INTO reports (period_start, period_end, total_cards, total_value, file_path)
                VALUES (?, ?, ?, ?, ?)
            """, (period_start, period_end, total_cards, total_value, file_path))
            return cursor.lastrowid

    def get_reports(self) -> List[Dict]:
        """Get all saved reports."""
        with self._lock, self._conn() as conn:
            rows = conn.execute("SELECT * FROM reports ORDER BY generated_at DESC").fetchall()
            return [dict(r) for r in rows]