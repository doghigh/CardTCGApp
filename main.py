import sys
import os
import sqlite3
import json
import re
import io
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QTableWidget, QTableWidgetItem,
    QTabWidget, QFileDialog, QMessageBox, QComboBox, QSpinBox,
    QDoubleSpinBox, QHeaderView, QSplitter, QGroupBox, QFormLayout, QDialog,
    QDialogButtonBox, QCheckBox, QStatusBar, QScrollArea, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap, QImage, QAction, QPalette, QColor

import cv2
import numpy as np
from PIL import Image
import requests
from bs4 import BeautifulSoup

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

try:
    import twain
    HAS_TWAIN = True
except ImportError:
    HAS_TWAIN = False

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    )
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

APP_NAME = "Trading Card Manager"
APP_VERSION = "1.0.0"
APP_DIR = Path(os.environ.get('APPDATA', Path.home())) / "TradingCardManager"
APP_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = APP_DIR / "cards.db"
SCANS_DIR = APP_DIR / "scans"
SCANS_DIR.mkdir(exist_ok=True)
REPORTS_DIR = APP_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


# ============================================================================
# DATABASE
# ============================================================================
class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _conn(self):
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self):
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
                CREATE INDEX IF NOT EXISTS idx_valuations_card ON valuations(card_id);
            """)

    def add_card(self, card: Dict) -> int:
        with self._lock, self._conn() as conn:
            cursor = conn.execute("""
                INSERT INTO cards (name, set_name, card_number, rarity, game, year,
                    language, foil, front_scan_path, back_scan_path, condition_grade,
                    condition_score, defects_json, estimated_value, purchase_price,
                    purchase_date, notes, quantity)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                card.get('name', 'Unknown'), card.get('set_name'), card.get('card_number'),
                card.get('rarity'), card.get('game'), card.get('year'),
                card.get('language', 'English'), int(card.get('foil', 0)),
                card.get('front_scan_path'), card.get('back_scan_path'),
                card.get('condition_grade'), card.get('condition_score'),
                json.dumps(card.get('defects', [])), card.get('estimated_value', 0),
                card.get('purchase_price', 0), card.get('purchase_date'),
                card.get('notes'), card.get('quantity', 1)
            ))
            return cursor.lastrowid

    def update_card(self, card_id: int, updates: Dict):
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
        with self._lock, self._conn() as conn:
            conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))

    def get_card(self, card_id: int) -> Optional[Dict]:
        with self._lock, self._conn() as conn:
            row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
            return dict(row) if row else None

    def get_all_cards(self, search: str = None) -> List[Dict]:
        with self._lock, self._conn() as conn:
            if search:
                rows = conn.execute("""
                    SELECT * FROM cards
                    WHERE name LIKE ? OR set_name LIKE ? OR game LIKE ?
                    ORDER BY updated_at DESC
                """, (f"%{search}%", f"%{search}%", f"%{search}%")).fetchall()
            else:
                rows = conn.execute("SELECT * FROM cards ORDER BY updated_at DESC").fetchall()
            return [dict(r) for r in rows]

    def add_valuation(self, card_id: int, source: str, value: float, url: str = None):
        with self._lock, self._conn() as conn:
            conn.execute("""
                INSERT INTO valuations (card_id, source, value, url)
                VALUES (?, ?, ?, ?)
            """, (card_id, source, value, url))

    def get_valuations(self, card_id: int) -> List[Dict]:
        with self._lock, self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM valuations WHERE card_id = ?
                ORDER BY fetched_at DESC
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
            return dict(row)

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


# ============================================================================
# SCANNER (TWAIN on Windows)
# ============================================================================
class ScannerInterface:
    def list_sources(self) -> List[str]:
        if not HAS_TWAIN:
            return []
        try:
            sm = twain.SourceManager(0)
            sources = sm.GetSourceList()
            sm.destroy()
            return list(sources)
        except Exception:
            return []

    def scan(self, source_name: Optional[str] = None, dpi: int = 300) -> Optional[np.ndarray]:
        if not HAS_TWAIN:
            return None
        try:
            sm = twain.SourceManager(0)
            src = sm.OpenSource(source_name) if source_name else sm.OpenSource()
            if not src:
                sm.destroy()
                return None
            try:
                src.SetCapability(twain.ICAP_XRESOLUTION, twain.TWTY_FIX32, float(dpi))
                src.SetCapability(twain.ICAP_YRESOLUTION, twain.TWTY_FIX32, float(dpi))
                src.SetCapability(twain.ICAP_PIXELTYPE, twain.TWTY_UINT16, twain.TWPT_RGB)
            except Exception:
                pass

            src.RequestAcquire(0, 0)
            handle = src.XferImageNatively()
            if not handle:
                src.destroy()
                sm.destroy()
                return None
            bmp_bytes = twain.DIBToBMFile(handle[0])
            img = Image.open(io.BytesIO(bmp_bytes))
            arr = np.array(img.convert('RGB'))
            src.destroy()
            sm.destroy()
            return arr
        except Exception as e:
            print(f"Scan error: {e}")
            return None

    def scan_from_file(self, path: str) -> Optional[np.ndarray]:
        try:
            img = cv2.imread(path)
            if img is None:
                pil = Image.open(path).convert('RGB')
                return np.array(pil)
            return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        except Exception:
            return None


# ============================================================================
# DEFECT DETECTION & CONDITION GRADING
# ============================================================================
class CardInspector:
    GRADES = {
        'Gem Mint': (95, 100),
        'Mint': (90, 94),
        'Near Mint': (80, 89),
        'Excellent': (70, 79),
        'Very Good': (60, 69),
        'Good': (50, 59),
        'Played': (35, 49),
        'Poor': (0, 34),
    }

    def _detect_card_region(self, img: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return img
        largest = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest)
        if w < 50 or h < 50:
            return img
        return img[y:y+h, x:x+w]

    def _detect_corner_damage(self, img: np.ndarray) -> List[Dict]:
        h, w = img.shape[:2]
        corner_size = max(10, min(h, w) // 8)
        corners = {
            'top_left': img[0:corner_size, 0:corner_size],
            'top_right': img[0:corner_size, max(0, w-corner_size):w],
            'bottom_left': img[max(0, h-corner_size):h, 0:corner_size],
            'bottom_right': img[max(0, h-corner_size):h, max(0, w-corner_size):w],
        }
        defects = []
        for name, region in corners.items():
            if region.size == 0:
                continue
            gray = cv2.cvtColor(region, cv2.COLOR_RGB2GRAY) if len(region.shape) == 3 else region
            ratio = np.sum(gray > 230) / gray.size
            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.sum(edges > 0) / edges.size

            if ratio > 0.35:
                severity = 'severe' if ratio > 0.6 else 'moderate' if ratio > 0.45 else 'minor'
                defects.append({
                    'type': 'corner_whitening', 'location': name,
                    'severity': severity, 'metric': round(float(ratio), 3),
                })
            if edge_density > 0.25:
                defects.append({
                    'type': 'corner_fraying', 'location': name,
                    'severity': 'moderate' if edge_density > 0.4 else 'minor',
                    'metric': round(float(edge_density), 3),
                })
        return defects

    def _detect_edge_wear(self, img: np.ndarray) -> List[Dict]:
        h, w = img.shape[:2]
        et = max(3, min(h, w) // 60)
        regions = {
            'top': img[0:et, :],
            'bottom': img[max(0, h-et):h, :],
            'left': img[:, 0:et],
            'right': img[:, max(0, w-et):w],
        }
        defects = []
        for name, region in regions.items():
            if region.size == 0:
                continue
            gray = cv2.cvtColor(region, cv2.COLOR_RGB2GRAY) if len(region.shape) == 3 else region
            white_ratio = np.sum(gray > 230) / gray.size
            if white_ratio > 0.30:
                severity = 'severe' if white_ratio > 0.55 else 'moderate' if white_ratio > 0.40 else 'minor'
                defects.append({
                    'type': 'edge_whitening', 'location': name,
                    'severity': severity, 'metric': round(float(white_ratio), 3),
                })
        return defects

    def _detect_surface_defects(self, img: np.ndarray) -> List[Dict]:
        defects = []
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
        h, w = gray.shape
        crop = max(10, min(h, w) // 20)
        center = gray[crop:max(crop+1, h-crop), crop:max(crop+1, w-crop)]
        if center.size == 0:
            return defects

        edges = cv2.Canny(center, 60, 180)
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=80,
                                minLineLength=min(h, w)//4, maxLineGap=10)
        if lines is not None and len(lines) > 0:
            long_lines = []
            for l in lines:
                x1, y1, x2, y2 = l[0]
                if np.hypot(x2-x1, y2-y1) > min(h, w) // 3:
                    long_lines.append(l)
            if long_lines:
                severity = 'severe' if len(long_lines) > 3 else 'moderate' if len(long_lines) > 1 else 'minor'
                defects.append({
                    'type': 'surface_crease_or_scratch', 'location': 'center',
                    'severity': severity, 'metric': len(long_lines),
                })

        if len(img.shape) == 3:
            hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
            sat = hsv[:, :, 1]
            val = hsv[:, :, 2]
            dark_anomaly = np.sum((val < 60) & (sat < 50)) / val.size
            if dark_anomaly > 0.08:
                defects.append({
                    'type': 'surface_staining', 'location': 'center',
                    'severity': 'moderate' if dark_anomaly > 0.15 else 'minor',
                    'metric': round(float(dark_anomaly), 3),
                })

        lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        if lap_var < 50:
            defects.append({
                'type': 'low_sharpness', 'location': 'overall',
                'severity': 'minor', 'metric': round(float(lap_var), 2),
            })
        return defects

    def _detect_centering(self, img: np.ndarray) -> Tuple[List[Dict], float]:
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
        col_sum = np.sum(thresh, axis=0)
        row_sum = np.sum(thresh, axis=1)

        def find_inner(arr):
            mx = arr.max() if arr.max() > 0 else 1
            mask = arr > mx * 0.3
            idx = np.where(mask)[0]
            if len(idx) == 0:
                return 0, len(arr)
            return int(idx[0]), int(idx[-1])

        left, right = find_inner(col_sum)
        top, bottom = find_inner(row_sum)
        lb, rb, tb, bb = left, w - right, top, h - bottom

        def ratio(a, b):
            return min(a, b) / max(a, b) if max(a, b) > 0 else 1.0

        h_c = ratio(lb, rb)
        v_c = ratio(tb, bb)
        score = (h_c + v_c) / 2 * 100

        defects = []
        if score < 70:
            severity = 'severe' if score < 50 else 'moderate' if score < 60 else 'minor'
            defects.append({
                'type': 'off_centering', 'location': f'h:{h_c:.2f}/v:{v_c:.2f}',
                'severity': severity, 'metric': round(float(score), 1),
            })
        return defects, float(score)

    def inspect(self, img: np.ndarray) -> Dict:
        if img is None or img.size == 0:
            return {'grade': 'Unknown', 'score': 0, 'defects': [], 'centering_score': 0}

        cropped = self._detect_card_region(img)
        defects = []
        defects.extend(self._detect_corner_damage(cropped))
        defects.extend(self._detect_edge_wear(cropped))
        defects.extend(self._detect_surface_defects(cropped))
        cd, cs = self._detect_centering(cropped)
        defects.extend(cd)

        score = 100.0
        penalty = {'minor': 3, 'moderate': 8, 'severe': 18}
        for d in defects:
            score -= penalty.get(d.get('severity', 'minor'), 3)
        score -= (100 - cs) * 0.15
        score = max(0, min(100, score))

        grade = 'Poor'
        for g, (lo, hi) in self.GRADES.items():
            if lo <= score <= hi:
                grade = g
                break

        return {
            'grade': grade,
            'score': round(score, 1),
            'defects': defects,
            'centering_score': round(cs, 1),
        }


# ============================================================================
# OCR
# ============================================================================
class CardIdentifier:
    def extract_text(self, img: np.ndarray) -> str:
        if not HAS_TESSERACT or img is None:
            return ""
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
            gray = cv2.resize(gray, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            return pytesseract.image_to_string(thresh).strip()
        except Exception:
            return ""

    def parse_card_info(self, text: str) -> Dict:
        info = {'name': None, 'set_name': None, 'card_number': None}
        if not text:
            return info
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        if lines:
            info['name'] = lines[0][:100]
        m = re.search(r'(\d+)\s*/\s*(\d+)', text)
        if m:
            info['card_number'] = m.group(0)
        return info


# ============================================================================
# VALUATION
# ============================================================================
class CardValuator:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
        })
        self.timeout = 10

    def search_tcgplayer(self, card_name: str, set_name: str = None) -> Optional[Dict]:
        try:
            query = card_name + (f" {set_name}" if set_name else "")
            url = f"https://www.tcgplayer.com/search/all/product?q={requests.utils.quote(query)}"
            r = self.session.get(url, timeout=self.timeout)
            if r.status_code != 200:
                return None
            soup = BeautifulSoup(r.text, 'html.parser')
            price_el = soup.find(class_=re.compile(r'price', re.I))
            if price_el:
                m = re.search(r'\$?([\d,]+\.\d{2})', price_el.get_text(strip=True))
                if m:
                    return {'source': 'TCGPlayer',
                            'value': float(m.group(1).replace(',', '')), 'url': url}
        except Exception:
            pass
        return None

    def search_ebay_sold(self, card_name: str, set_name: str = None) -> Optional[Dict]:
        try:
            query = card_name + (f" {set_name}" if set_name else "") + " card"
            url = (f"https://www.ebay.com/sch/i.html?_nkw={requests.utils.quote(query)}"
                   f"&LH_Sold=1&LH_Complete=1")
            r = self.session.get(url, timeout=self.timeout)
            if r.status_code != 200:
                return None
            soup = BeautifulSoup(r.text, 'html.parser')
            prices = []
            for el in soup.select('.s-item__price'):
                for m in re.finditer(r'\$([\d,]+\.\d{2})', el.get_text(strip=True)):
                    try:
                        prices.append(float(m.group(1).replace(',', '')))
                    except ValueError:
                        pass
            if prices:
                prices.sort()
                trimmed = prices[len(prices)//4:max(len(prices)*3//4, 1)] or prices
                return {'source': 'eBay (sold)',
                        'value': round(sum(trimmed)/len(trimmed), 2), 'url': url}
        except Exception:
            pass
        return None

    def search_pricecharting(self, card_name: str, set_name: str = None) -> Optional[Dict]:
        try:
            query = card_name + (f" {set_name}" if set_name else "")
            url = f"https://www.pricecharting.com/search-products?q={requests.utils.quote(query)}&type=prices"
            r = self.session.get(url, timeout=self.timeout)
            if r.status_code != 200:
                return None
            soup = BeautifulSoup(r.text, 'html.parser')
            cell = soup.find('td', class_=re.compile(r'price|used_price'))
            if cell:
                m = re.search(r'\$([\d,]+\.\d{2})', cell.get_text())
                if m:
                    return {'source': 'PriceCharting',
                            'value': float(m.group(1).replace(',', '')), 'url': url}
        except Exception:
            pass
        return None

    def fetch_all_values(self, card_name: str, set_name: str = None) -> List[Dict]:
        sources = [self.search_tcgplayer, self.search_ebay_sold, self.search_pricecharting]
        results = []
        with ThreadPoolExecutor(max_workers=3) as ex:
            futures = [ex.submit(fn, card_name, set_name) for fn in sources]
            for f in futures:
                try:
                    res = f.result(timeout=15)
                    if res and res.get('value', 0) > 0:
                        results.append(res)
                except Exception:
                    pass
        return results

    def compute_estimate(self, values: List[Dict], condition_score: float) -> float:
        if not values:
            return 0.0
        prices = sorted(v['value'] for v in values)
        median = prices[len(prices) // 2]
        multiplier = max(0.2, min(1.2, condition_score / 85.0))
        return round(median * multiplier, 2)


# ============================================================================
# REPORT GENERATOR
# ============================================================================
class ReportGenerator:
    def __init__(self, db: Database):
        self.db = db

    def generate_monthly(self, year: int, month: int) -> Optional[Path]:
        if not HAS_REPORTLAB:
            return None

        start = datetime(year, month, 1)
        end = (datetime(year + 1, 1, 1) if month == 12
               else datetime(year, month + 1, 1)) - timedelta(seconds=1)

        period_cards = self.db.get_cards_for_period(
            start.strftime('%Y-%m-%d %H:%M:%S'),
            end.strftime('%Y-%m-%d %H:%M:%S'))
        all_cards = self.db.get_all_cards()
        stats = self.db.get_collection_stats()

        out_path = REPORTS_DIR / f"collection_report_{year}_{month:02d}.pdf"
        doc = SimpleDocTemplate(str(out_path), pagesize=letter,
                                 rightMargin=50, leftMargin=50,
                                 topMargin=50, bottomMargin=50)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('TitleCenter', parent=styles['Title'],
                                      alignment=1, textColor=colors.HexColor('#1a365d'))
        h2 = ParagraphStyle('H2', parent=styles['Heading2'],
                            textColor=colors.HexColor('#2c5282'))

        story = []
        story.append(Paragraph("Trading Card Collection Report", title_style))
        story.append(Paragraph(start.strftime('%B %Y'), styles['Heading2']))
        story.append(Spacer(1, 0.2 * inch))
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                                styles['Normal']))
        story.append(Spacer(1, 0.3 * inch))

        story.append(Paragraph("Collection Summary", h2))
        summary = [
            ['Metric', 'Value'],
            ['Total Unique Cards', f"{stats['total_cards']:,}"],
            ['Total Quantity', f"{stats['total_quantity']:,}"],
            ['Total Estimated Value', f"${stats['total_value']:,.2f}"],
            ['Total Cost Basis', f"${stats['total_cost']:,.2f}"],
            ['Net Position', f"${stats['total_value'] - stats['total_cost']:,.2f}"],
            ['Average Condition Score', f"{stats['avg_condition']:.1f}/100"],
        ]
        t = Table(summary, colWidths=[3*inch, 2.5*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1),
             [colors.HexColor('#f7fafc'), colors.white]),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.3 * inch))

        period_value = sum((c.get('estimated_value') or 0) * (c.get('quantity') or 1)
                           for c in period_cards)
        story.append(Paragraph("This Month's Activity", h2))
        story.append(Paragraph(
            f"Cards added this month: <b>{len(period_cards)}</b><br/>"
            f"Value added this month: <b>${period_value:,.2f}</b>",
            styles['Normal']))
        story.append(Spacer(1, 0.2 * inch))

        if period_cards:
            data = [['Name', 'Set', 'Grade', 'Qty', 'Value']]
            for c in period_cards[:30]:
                data.append([
                    (c.get('name') or '')[:30],
                    (c.get('set_name') or '')[:20],
                    c.get('condition_grade') or '-',
                    str(c.get('quantity', 1)),
                    f"${(c.get('estimated_value') or 0):.2f}",
                ])
            t = Table(data, colWidths=[2.2*inch, 1.6*inch, 1.0*inch, 0.5*inch, 0.9*inch])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1),
                 [colors.HexColor('#f7fafc'), colors.white]),
            ]))
            story.append(t)

        story.append(PageBreak())
        story.append(Paragraph("Top 25 Cards by Value", h2))
        sorted_cards = sorted(
            all_cards,
            key=lambda c: (c.get('estimated_value') or 0) * (c.get('quantity') or 1),
            reverse=True)[:25]
        if sorted_cards:
            data = [['#', 'Name', 'Set', 'Grade', 'Qty', 'Unit', 'Total']]
            for i, c in enumerate(sorted_cards, 1):
                qty = c.get('quantity', 1) or 1
                val = c.get('estimated_value', 0) or 0
                data.append([
                    str(i), (c.get('name') or '')[:25],
                    (c.get('set_name') or '')[:18],
                    c.get('condition_grade') or '-',
                    str(qty), f"${val:.2f}", f"${val * qty:.2f}",
                ])
            t = Table(data, colWidths=[0.3*inch, 1.9*inch, 1.4*inch, 0.9*inch,
                                        0.4*inch, 0.7*inch, 0.8*inch])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1),
                 [colors.HexColor('#f7fafc'), colors.white]),
                ('ALIGN', (4, 0), (-1, -1), 'RIGHT'),
            ]))
            story.append(t)

        story.append(Spacer(1, 0.3 * inch))
        story.append(Paragraph("Condition Distribution", h2))
        grade_counts = {}
        for c in all_cards:
            g = c.get('condition_grade') or 'Ungraded'
            grade_counts[g] = grade_counts.get(g, 0) + (c.get('quantity') or 1)
        if grade_counts:
            data = [['Grade', 'Count']]
            for g, count in sorted(grade_counts.items(), key=lambda x: -x[1]):
                data.append([g, str(count)])
            t = Table(data, colWidths=[3*inch, 1.5*inch])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1),
                 [colors.HexColor('#f7fafc'), colors.white]),
            ]))
            story.append(t)

        doc.build(story)
        self.db.save_report(start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'),
                            len(period_cards), period_value, str(out_path))
        return out_path


# ============================================================================
# WORKER THREADS
# ============================================================================
class ScanWorker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, scanner: ScannerInterface, source_name: str = None,
                 file_path: str = None, dpi: int = 300):
        super().__init__()
        self.scanner = scanner
        self.source_name = source_name
        self.file_path = file_path
        self.dpi = dpi

    def run(self):
        try:
            if self.file_path:
                self.progress.emit("Loading image...")
                img = self.scanner.scan_from_file(self.file_path)
            else:
                self.progress.emit("Scanning from device...")
                img = self.scanner.scan(self.source_name, self.dpi)
            if img is None:
                self.error.emit("Scan failed - no image captured.")
                return
            self.finished.emit(img)
        except Exception as e:
            self.error.emit(str(e))


class ValuationWorker(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, valuator: CardValuator, name: str, set_name: str = None):
        super().__init__()
        self.valuator = valuator
        self.name = name
        self.set_name = set_name

    def run(self):
        try:
            self.progress.emit("Querying TCGPlayer, eBay, PriceCharting...")
            results = self.valuator.fetch_all_values(self.name, self.set_name)
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


# ============================================================================
# UI WIDGETS
# ============================================================================
class ImageViewer(QLabel):
    def __init__(self, placeholder="No image"):
        super().__init__()
        self.setMinimumSize(280, 380)
        self.setMaximumSize(450, 600)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            QLabel { background: #1a202c; color: #718096;
                     border: 2px dashed #2d3748; border-radius: 8px; font-size: 13px; }
        """)
        self._placeholder = placeholder
        self.setText(placeholder)

    def set_image(self, img):
        if img is None:
            self.setText(self._placeholder)
            self.setPixmap(QPixmap())
            return
        if len(img.shape) == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        h, w = img.shape[:2]
        qimg = QImage(img.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        scaled = pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        self.setPixmap(scaled)


class ScanTab(QWidget):
    card_added = pyqtSignal(int)

    def __init__(self, db, scanner, inspector, identifier, valuator):
        super().__init__()
        self.db = db
        self.scanner = scanner
        self.inspector = inspector
        self.identifier = identifier
        self.valuator = valuator
        self.current_front_img = None
        self.current_back_img = None
        self.current_inspection = None
        self.current_valuations = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        bar = QHBoxLayout()
        self.source_combo = QComboBox()
        self.source_combo.setMinimumWidth(220)
        sources = self.scanner.list_sources()
        if sources:
            self.source_combo.addItems(sources)
        else:
            self.source_combo.addItem("(no TWAIN scanner detected)")

        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 1200)
        self.dpi_spin.setValue(300)
        self.dpi_spin.setSuffix(" DPI")

        self.scan_front_btn = QPushButton("📷 Scan Front")
        self.scan_back_btn = QPushButton("🔄 Scan Back")
        self.load_front_btn = QPushButton("📂 Load Front")
        self.load_back_btn = QPushButton("📂 Load Back")

        for btn in [self.scan_front_btn, self.scan_back_btn,
                    self.load_front_btn, self.load_back_btn]:
            btn.setMinimumHeight(36)

        self.scan_front_btn.clicked.connect(lambda: self._scan('front'))
        self.scan_back_btn.clicked.connect(lambda: self._scan('back'))
        self.load_front_btn.clicked.connect(lambda: self._load_file('front'))
        self.load_back_btn.clicked.connect(lambda: self._load_file('back'))

        bar.addWidget(QLabel("Scanner:"))
        bar.addWidget(self.source_combo)
        bar.addWidget(self.dpi_spin)
        bar.addWidget(self.scan_front_btn)
        bar.addWidget(self.scan_back_btn)
        bar.addWidget(self.load_front_btn)
        bar.addWidget(self.load_back_btn)
        bar.addStretch()
        layout.addLayout(bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        img_widget = QWidget()
        img_layout = QHBoxLayout(img_widget)
        front_box = QGroupBox("Front")
        fl = QVBoxLayout(front_box)
        self.front_view = ImageViewer("Front side\nNot scanned yet")
        fl.addWidget(self.front_view)
        back_box = QGroupBox("Back")
        bl = QVBoxLayout(back_box)
        self.back_view = ImageViewer("Back side\nNot scanned yet")
        bl.addWidget(self.back_view)
        img_layout.addWidget(front_box)
        img_layout.addWidget(back_box)
        splitter.addWidget(img_widget)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setSpacing(10)

        details_group = QGroupBox("Card Details")
        form = QFormLayout(details_group)
        self.name_edit = QLineEdit()
        self.set_edit = QLineEdit()
        self.number_edit = QLineEdit()
        self.rarity_edit = QLineEdit()
        self.game_edit = QComboBox()
        self.game_edit.setEditable(True)
        self.game_edit.addItems([
            "Magic: The Gathering", "Pokémon", "Yu-Gi-Oh!", "One Piece",
            "Lorcana", "Flesh and Blood", "Sports", "Other"
        ])
        self.year_spin = QSpinBox()
        self.year_spin.setRange(1900, 2100)
        self.year_spin.setValue(datetime.now().year)
        self.lang_edit = QLineEdit("English")
        self.foil_check = QCheckBox("Foil / Holographic")
        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 9999)
        self.qty_spin.setValue(1)
        self.purchase_spin = QDoubleSpinBox()
        self.purchase_spin.setRange(0, 999999)
        self.purchase_spin.setPrefix("$")
        self.purchase_spin.setDecimals(2)
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(60)

        form.addRow("Name:", self.name_edit)
        form.addRow("Set:", self.set_edit)
        form.addRow("Card #:", self.number_edit)
        form.addRow("Rarity:", self.rarity_edit)
        form.addRow("Game:", self.game_edit)
        form.addRow("Year:", self.year_spin)
        form.addRow("Language:", self.lang_edit)
        form.addRow("Foil:", self.foil_check)
        form.addRow("Quantity:", self.qty_spin)
        form.addRow("Purchase Price:", self.purchase_spin)
        form.addRow("Notes:", self.notes_edit)
        right_layout.addWidget(details_group)

        insp_group = QGroupBox("Inspection")
        il = QVBoxLayout(insp_group)
        self.grade_label = QLabel("Not inspected")
        self.grade_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.score_label = QLabel("Score: -")
        self.defects_text = QTextEdit()
        self.defects_text.setReadOnly(True)
        self.defects_text.setMaximumHeight(110)
        self.inspect_btn = QPushButton("🔍 Re-inspect")
        self.inspect_btn.clicked.connect(self._inspect)
        il.addWidget(self.grade_label)
        il.addWidget(self.score_label)
        il.addWidget(self.defects_text)
        il.addWidget(self.inspect_btn)
        right_layout.addWidget(insp_group)

        val_group = QGroupBox("Valuation")
        vl = QVBoxLayout(val_group)
        self.value_label = QLabel("Estimate: -")
        self.value_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #38a169;")
        self.value_text = QTextEdit()
        self.value_text.setReadOnly(True)
        self.value_text.setMaximumHeight(110)
        self.fetch_value_btn = QPushButton("💰 Fetch Online Values")
        self.fetch_value_btn.clicked.connect(self._fetch_value)
        vl.addWidget(self.value_label)
        vl.addWidget(self.value_text)
        vl.addWidget(self.fetch_value_btn)
        right_layout.addWidget(val_group)

        self.save_btn = QPushButton("💾 Save Card to Collection")
        self.save_btn.setMinimumHeight(44)
        self.save_btn.setStyleSheet("""
            QPushButton { background: #2c5282; color: white;
                font-size: 14px; font-weight: bold; border-radius: 6px; }
            QPushButton:hover { background: #2b6cb0; }
            QPushButton:disabled { background: #4a5568; }
        """)
        self.save_btn.clicked.connect(self._save_card)
        right_layout.addWidget(self.save_btn)
        right_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(right)
        splitter.addWidget(scroll)
        splitter.setSizes([700, 500])
        layout.addWidget(splitter)

        self.status_label = QLabel("Ready.")
        self.status_label.setStyleSheet("color: #a0aec0; padding: 4px;")
        layout.addWidget(self.status_label)

    def _scan(self, side: str):
        source = self.source_combo.currentText()
        if "no TWAIN" in source:
            QMessageBox.warning(self, "No Scanner",
                "No TWAIN-compatible scanner detected.\n\n"
                "Use 'Load Front' / 'Load Back' to load image files instead.")
            return
        self.status_label.setText(f"Scanning {side}...")
        self.scan_front_btn.setEnabled(False)
        self.scan_back_btn.setEnabled(False)
        self._worker = ScanWorker(self.scanner, source_name=source, dpi=self.dpi_spin.value())
        self._worker.finished.connect(lambda img: self._scan_done(side, img))
        self._worker.error.connect(self._scan_error)
        self._worker.progress.connect(self.status_label.setText)
        self._worker.start()

    def _load_file(self, side: str):
        path, _ = QFileDialog.getOpenFileName(
            self, f"Load {side} image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tiff *.tif)")
        if not path:
            return
        self.status_label.setText(f"Loading {side}...")
        self._worker = ScanWorker(self.scanner, file_path=path)
        self._worker.finished.connect(lambda img: self._scan_done(side, img))
        self._worker.error.connect(self._scan_error)
        self._worker.start()

    def _scan_done(self, side: str, img):
        self.scan_front_btn.setEnabled(True)
        self.scan_back_btn.setEnabled(True)
        if side == 'front':
            self.current_front_img = img
            self.front_view.set_image(img)
            self._auto_identify(img)
            self._inspect()
        else:
            self.current_back_img = img
            self.back_view.set_image(img)
        self.status_label.setText(f"{side.capitalize()} captured.")

    def _scan_error(self, msg: str):
        self.scan_front_btn.setEnabled(True)
        self.scan_back_btn.setEnabled(True)
        self.status_label.setText(f"Error: {msg}")
        QMessageBox.critical(self, "Scan Error", msg)

    def _auto_identify(self, img):
        text = self.identifier.extract_text(img)
        info = self.identifier.parse_card_info(text)
        if info.get('name') and not self.name_edit.text():
            self.name_edit.setText(info['name'])
        if info.get('card_number') and not self.number_edit.text():
            self.number_edit.setText(info['card_number'])

    def _inspect(self):
        if self.current_front_img is None:
            self.status_label.setText("Scan or load a front image first.")
            return
        result = self.inspector.inspect(self.current_front_img)
        self.current_inspection = result
        self.grade_label.setText(f"Grade: {result['grade']}")
        self.score_label.setText(
            f"Score: {result['score']}/100   |   Centering: {result.get('centering_score', 0)}/100")
        if result['defects']:
            lines = [f"• [{d['severity'].upper()}] {d['type'].replace('_', ' ').title()} "
                     f"@ {d['location']} (metric: {d.get('metric', '-')})"
                     for d in result['defects']]
            self.defects_text.setPlainText('\n'.join(lines))
        else:
            self.defects_text.setPlainText("No defects detected.")

    def _fetch_value(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.information(self, "Missing", "Enter a card name first.")
            return
        self.fetch_value_btn.setEnabled(False)
        self.status_label.setText("Fetching values from online sources...")
        self._val_worker = ValuationWorker(self.valuator, name, self.set_edit.text().strip())
        self._val_worker.finished.connect(self._values_done)
        self._val_worker.error.connect(self._values_error)
        self._val_worker.progress.connect(self.status_label.setText)
        self._val_worker.start()

    def _values_done(self, results: List[Dict]):
        self.fetch_value_btn.setEnabled(True)
        self.current_valuations = results
        if not results:
            self.value_text.setPlainText("No values found from online sources.")
            self.value_label.setText("Estimate: $0.00")
            self.status_label.setText("Valuation finished (no results).")
            return

        condition_score = self.current_inspection['score'] if self.current_inspection else 85
        estimate = self.valuator.compute_estimate(results, condition_score)
        self.value_label.setText(f"Estimate: ${estimate:.2f}")
        lines = [f"Adjusted by condition score {condition_score:.0f}/100\n"]
        for r in results:
            lines.append(f"• {r['source']}: ${r['value']:.2f}")
        self.value_text.setPlainText('\n'.join(lines))
        self.status_label.setText(f"Found {len(results)} sources. Estimate: ${estimate:.2f}")

    def _values_error(self, msg: str):
        self.fetch_value_btn.setEnabled(True)
        self.status_label.setText(f"Valuation error: {msg}")

    def _save_card(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Missing", "Card must have a name.")
            return

        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        front_path = back_path = None
        if self.current_front_img is not None:
            front_path = str(SCANS_DIR / f"card_{ts}_front.png")
            cv2.imwrite(front_path, cv2.cvtColor(self.current_front_img, cv2.COLOR_RGB2BGR))
        if self.current_back_img is not None:
            back_path = str(SCANS_DIR / f"card_{ts}_back.png")
            cv2.imwrite(back_path, cv2.cvtColor(self.current_back_img, cv2.COLOR_RGB2BGR))

        condition_score = self.current_inspection['score'] if self.current_inspection else None
        estimate = 0.0
        if self.current_valuations:
            estimate = self.valuator.compute_estimate(
                self.current_valuations,
                condition_score if condition_score is not None else 85)

        card_data = {
            'name': self.name_edit.text().strip(),
            'set_name': self.set_edit.text().strip(),
            'card_number': self.number_edit.text().strip(),
            'rarity': self.rarity_edit.text().strip(),
            'game': self.game_edit.currentText().strip(),
            'year': self.year_spin.value(),
            'language': self.lang_edit.text().strip() or 'English',
            'foil': self.foil_check.isChecked(),
            'front_scan_path': front_path,
            'back_scan_path': back_path,
            'condition_grade': self.current_inspection['grade'] if self.current_inspection else None,
            'condition_score': condition_score,
            'defects': self.current_inspection['defects'] if self.current_inspection else [],
            'estimated_value': estimate,
            'purchase_price': self.purchase_spin.value(),
            'purchase_date': datetime.now().strftime('%Y-%m-%d'),
            'notes': self.notes_edit.toPlainText().strip(),
            'quantity': self.qty_spin.value(),
        }
        card_id = self.db.add_card(card_data)
        for v in self.current_valuations:
            self.db.add_valuation(card_id, v['source'], v['value'], v.get('url'))

        self.status_label.setText(f"✅ Saved card #{card_id}: {card_data['name']}")
        QMessageBox.information(self, "Saved",
            f"Card '{card_data['name']}' added to collection.\n"
            f"Estimated value: ${estimate:.2f}")
        self.card_added.emit(card_id)
        self._reset()

    def _reset(self):
        self.current_front_img = None
        self.current_back_img = None
        self.current_inspection = None
        self.current_valuations = []
        self.front_view.set_image(None)
        self.back_view.set_image(None)
        self.name_edit.clear()
        self.set_edit.clear()
        self.number_edit.clear()
        self.rarity_edit.clear()
        self.qty_spin.setValue(1)
        self.purchase_spin.setValue(0)
        self.notes_edit.clear()
        self.foil_check.setChecked(False)
        self.grade_label.setText("Not inspected")
        self.score_label.setText("Score: -")
        self.defects_text.clear()
        self.value_label.setText("Estimate: -")
        self.value_text.clear()


class CollectionTab(QWidget):
    def __init__(self, db: Database, valuator: CardValuator):
        super().__init__()
        self.db = db
        self.valuator = valuator
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        bar = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔎 Search by name, set, or game...")
        self.search_edit.textChanged.connect(self.refresh)
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self.refresh)
        self.delete_btn = QPushButton("🗑 Delete Selected")
        self.delete_btn.clicked.connect(self._delete_selected)
        self.revalue_btn = QPushButton("💰 Re-value Selected")
        self.revalue_btn.clicked.connect(self._revalue_selected)
        self.export_btn = QPushButton("📤 Export CSV")
        self.export_btn.clicked.connect(self._export_csv)
        bar.addWidget(self.search_edit)
        bar.addWidget(self.refresh_btn)
        bar.addWidget(self.revalue_btn)
        bar.addWidget(self.delete_btn)
        bar.addWidget(self.export_btn)
        layout.addLayout(bar)

        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("""
            background: #2c5282; color: white;
            padding: 12px; border-radius: 6px; font-size: 13px;
        """)
        layout.addWidget(self.stats_label)

        self.table = QTableWidget()
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels([
            "ID", "Name", "Set", "Card #", "Game", "Grade",
            "Score", "Qty", "Unit Value", "Total Value", "Added"
        ])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.doubleClicked.connect(self._show_detail)
        layout.addWidget(self.table)

    def refresh(self):
        search = self.search_edit.text().strip() or None
        cards = self.db.get_all_cards(search)
        stats = self.db.get_collection_stats()

        self.stats_label.setText(
            f"📦 <b>{stats['total_cards']}</b> unique cards  •  "
            f"<b>{stats['total_quantity']}</b> total cards  •  "
            f"💰 Total value: <b>${stats['total_value']:,.2f}</b>  •  "
            f"💵 Cost basis: <b>${stats['total_cost']:,.2f}</b>  •  "
            f"📈 Net: <b>${stats['total_value'] - stats['total_cost']:+,.2f}</b>  •  "
            f"⭐ Avg condition: <b>{stats['avg_condition']:.1f}/100</b>"
        )

        self.table.setRowCount(len(cards))
        for i, c in enumerate(cards):
            qty = c.get('quantity', 1) or 1
            val = c.get('estimated_value', 0) or 0
            cells = [
                str(c['id']),
                c.get('name', '') or '',
                c.get('set_name', '') or '',
                c.get('card_number', '') or '',
                c.get('game', '') or '',
                c.get('condition_grade', '') or '',
                f"{c.get('condition_score', 0) or 0:.1f}",
                str(qty),
                f"${val:.2f}",
                f"${val * qty:.2f}",
                (c.get('created_at', '') or '')[:10],
            ]
            for j, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if j == 6:
                    score = c.get('condition_score', 0) or 0
                    if score >= 90:
                        item.setForeground(QColor("#38a169"))
                    elif score >= 70:
                        item.setForeground(QColor("#d69e2e"))
                    else:
                        item.setForeground(QColor("#e53e3e"))
                self.table.setItem(i, j, item)

    def _selected_ids(self) -> List[int]:
        rows = set(idx.row() for idx in self.table.selectedIndexes())
        ids = []
        for r in rows:
            item = self.table.item(r, 0)
            if item:
                try:
                    ids.append(int(item.text()))
                except ValueError:
                    pass
        return ids

    def _delete_selected(self):
        ids = self._selected_ids()
        if not ids:
            return
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete {len(ids)} card(s) from your collection?\nThis cannot be undone.")
        if reply == QMessageBox.StandardButton.Yes:
            for cid in ids:
                self.db.delete_card(cid)
            self.refresh()

    def _revalue_selected(self):
        ids = self._selected_ids()
        if not ids:
            return
        QMessageBox.information(self, "Re-valuing",
            f"Re-fetching online values for {len(ids)} card(s) in background...")
        threading.Thread(target=self._revalue_worker, args=(ids,), daemon=True).start()

    def _revalue_worker(self, ids: List[int]):
        for cid in ids:
            card = self.db.get_card(cid)
            if not card:
                continue
            results = self.valuator.fetch_all_values(card['name'], card.get('set_name'))
            if not results:
                continue
            score = card.get('condition_score') or 85
            estimate = self.valuator.compute_estimate(results, score)
            self.db.update_card(cid, {'estimated_value': estimate})
            for r in results:
                self.db.add_valuation(cid, r['source'], r['value'], r.get('url'))
        QTimer.singleShot(0, self.refresh)

    def _show_detail(self):
        ids = self._selected_ids()
        if not ids:
            return
        card = self.db.get_card(ids[0])
        if not card:
            return
        valuations = self.db.get_valuations(card['id'])
        dlg = CardDetailDialog(card, valuations, self)
        dlg.exec()

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Collection", str(APP_DIR / "collection.csv"), "CSV (*.csv)")
        if not path:
            return
        cards = self.db.get_all_cards()
        import csv
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'ID', 'Name', 'Set', 'Number', 'Rarity', 'Game', 'Year',
                'Language', 'Foil', 'Grade', 'Score', 'Quantity',
                'Estimated Value', 'Purchase Price', 'Total Value', 'Added'
            ])
            for c in cards:
                qty = c.get('quantity', 1) or 1
                val = c.get('estimated_value', 0) or 0
                writer.writerow([
                    c['id'], c.get('name'), c.get('set_name'), c.get('card_number'),
                    c.get('rarity'), c.get('game'), c.get('year'),
                    c.get('language'), c.get('foil'), c.get('condition_grade'),
                    c.get('condition_score'), qty, val, c.get('purchase_price'),
                    val * qty, c.get('created_at'),
                ])
        QMessageBox.information(self, "Exported", f"Collection exported to:\n{path}")


class CardDetailDialog(QDialog):
    def __init__(self, card: Dict, valuations: List[Dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Card #{card['id']} - {card.get('name', 'Unknown')}")
        self.resize(900, 700)
        layout = QHBoxLayout(self)

        img_panel = QVBoxLayout()
        for label, key in [("Front", 'front_scan_path'), ("Back", 'back_scan_path')]:
            grp = QGroupBox(label)
            gl = QVBoxLayout(grp)
            view = ImageViewer(f"No {label.lower()} scan")
            path = card.get(key)
            if path and os.path.exists(path):
                img = cv2.imread(path)
                if img is not None:
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    view.set_image(img)
            gl.addWidget(view)
            img_panel.addWidget(grp)
        layout.addLayout(img_panel)

        right = QVBoxLayout()
        info_text = QTextEdit()
        info_text.setReadOnly(True)
        try:
            defects = json.loads(card.get('defects_json') or '[]')
        except json.JSONDecodeError:
            defects = []

        defect_lines = '\n'.join([
            f"  • [{d.get('severity', '?').upper()}] {d.get('type', '').replace('_', ' ').title()} "
            f"@ {d.get('location', '?')}"
            for d in defects
        ]) or "  (none detected)"

        val_lines = '\n'.join([
            f"  • {v['source']}: ${v['value']:.2f} ({(v.get('fetched_at') or '')[:10]})"
            for v in valuations
        ]) or "  (no online valuations stored)"

        info_text.setHtml(f"""
            <h2>{card.get('name', 'Unknown')}</h2>
            <table cellpadding="4">
                <tr><td><b>Set:</b></td><td>{card.get('set_name') or '-'}</td></tr>
                <tr><td><b>Number:</b></td><td>{card.get('card_number') or '-'}</td></tr>
                <tr><td><b>Rarity:</b></td><td>{card.get('rarity') or '-'}</td></tr>
                <tr><td><b>Game:</b></td><td>{card.get('game') or '-'}</td></tr>
                <tr><td><b>Year:</b></td><td>{card.get('year') or '-'}</td></tr>
                <tr><td><b>Language:</b></td><td>{card.get('language') or '-'}</td></tr>
                <tr><td><b>Foil:</b></td><td>{'Yes' if card.get('foil') else 'No'}</td></tr>
                <tr><td><b>Quantity:</b></td><td>{card.get('quantity') or 1}</td></tr>
            </table>
            <h3>Condition</h3>
            <p><b>Grade:</b> {card.get('condition_grade') or '-'}<br>
               <b>Score:</b> {card.get('condition_score') or 0}/100</p>
            <h3>Defects</h3>
            <pre>{defect_lines}</pre>
            <h3>Valuations</h3>
            <pre>{val_lines}</pre>
            <h3>Financial</h3>
            <p><b>Estimated Value:</b> ${card.get('estimated_value') or 0:.2f}<br>
               <b>Purchase Price:</b> ${card.get('purchase_price') or 0:.2f}<br>
               <b>Net per card:</b> ${(card.get('estimated_value') or 0) - (card.get('purchase_price') or 0):.2f}</p>
            <h3>Notes</h3>
            <p>{card.get('notes') or '-'}</p>
        """)
        right.addWidget(info_text)
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(self.reject)
        btn_box.accepted.connect(self.accept)
        right.addWidget(btn_box)
        layout.addLayout(right)


class ReportsTab(QWidget):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.report_gen = ReportGenerator(db)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Year:"))
        self.year_spin = QSpinBox()
        self.year_spin.setRange(2000, 2100)
        self.year_spin.setValue(datetime.now().year)
        bar.addWidget(self.year_spin)
        bar.addWidget(QLabel("Month:"))
        self.month_combo = QComboBox()
        for i, m in enumerate(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'], 1):
            self.month_combo.addItem(m, i)
        self.month_combo.setCurrentIndex(datetime.now().month - 1)
        bar.addWidget(self.month_combo)
        self.gen_btn = QPushButton("📄 Generate Monthly PDF Report")
        self.gen_btn.setMinimumHeight(36)
        self.gen_btn.clicked.connect(self._generate)
        bar.addWidget(self.gen_btn)
        bar.addStretch()
        layout.addLayout(bar)

        self.report_list = QListWidget()
        self.report_list.itemDoubleClicked.connect(self._open_report)
        layout.addWidget(QLabel("📚 Past Reports (double-click to open):"))
        layout.addWidget(self.report_list)

    def refresh(self):
        self.report_list.clear()
        for r in self.db.get_reports():
            text = (f"{r['period_start']} → {r['period_end']}  •  "
                    f"{r['total_cards']} cards added  •  "
                    f"${r['total_value']:.2f}  •  {r['file_path']}")
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, r['file_path'])
            self.report_list.addItem(item)

    def _generate(self):
        if not HAS_REPORTLAB:
            QMessageBox.warning(self, "Missing Dependency",
                "reportlab is required for PDF reports.\nInstall with: pip install reportlab")
            return
        year = self.year_spin.value()
        month = self.month_combo.currentData()
        try:
            path = self.report_gen.generate_monthly(year, month)
            if path:
                QMessageBox.information(self, "Report Generated", f"Report saved to:\n{path}")
                self.refresh()
                if hasattr(os, 'startfile'):
                    os.startfile(str(path))
            else:
                QMessageBox.warning(self, "Failed", "Report generation returned no file.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate report:\n{e}")

    def _open_report(self, item: QListWidgetItem):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and os.path.exists(path):
            if hasattr(os, 'startfile'):
                os.startfile(path)
        else:
            QMessageBox.warning(self, "Not Found", f"Report file missing:\n{path}")


# ============================================================================
# MAIN WINDOW
# ============================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1500, 950)

        self.db = Database(DB_PATH)
        self.scanner = ScannerInterface()
        self.inspector = CardInspector()
        self.identifier = CardIdentifier()
        self.valuator = CardValuator()

        tabs = QTabWidget()
        tabs.setDocumentMode(True)

        self.scan_tab = ScanTab(self.db, self.scanner, self.inspector,
                                 self.identifier, self.valuator)
        self.collection_tab = CollectionTab(self.db, self.valuator)
        self.reports_tab = ReportsTab(self.db)

        self.scan_tab.card_added.connect(lambda _: self.collection_tab.refresh())
        self.scan_tab.card_added.connect(lambda _: self.reports_tab.refresh())

        tabs.addTab(self.scan_tab, "🃏 Scan & Add")
        tabs.addTab(self.collection_tab, "📦 Collection")
        tabs.addTab(self.reports_tab, "📊 Reports")

        self.setCentralWidget(tabs)

        sb = QStatusBar()
        self.setStatusBar(sb)
        twain_status = "TWAIN ✅" if HAS_TWAIN else "TWAIN ❌"
        ocr_status = "OCR ✅" if HAS_TESSERACT else "OCR ❌"
        pdf_status = "PDF ✅" if HAS_REPORTLAB else "PDF ❌"
        sb.showMessage(
            f"Database: {DB_PATH}  |  {twain_status}  |  {ocr_status}  |  {pdf_status}")

        menu = self.menuBar()
        file_menu = menu.addMenu("&File")
        open_dir = QAction("Open Data Folder", self)
        open_dir.triggered.connect(lambda: os.startfile(str(APP_DIR))
                                   if hasattr(os, 'startfile') else None)
        file_menu.addAction(open_dir)
        file_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        help_menu = menu.addMenu("&Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self._about)
        help_menu.addAction(about_action)

    def _about(self):
        QMessageBox.about(self, f"About {APP_NAME}",
            f"<h2>{APP_NAME} v{APP_VERSION}</h2>"
            f"<p>Windows-native trading card collection manager.</p>"
            f"<p>Scans cards via TWAIN, inspects for damage, fetches values from "
            f"TCGPlayer / eBay / PriceCharting, and generates monthly PDF reports.</p>"
            f"<p><b>Data folder:</b> {APP_DIR}</p>")


def apply_dark_theme(app: QApplication):
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(30, 32, 40))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(220, 224, 230))
    palette.setColor(QPalette.ColorRole.Base, QColor(22, 24, 30))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(38, 40, 48))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(220, 224, 230))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(220, 224, 230))
    palette.setColor(QPalette.ColorRole.Text, QColor(220, 224, 230))
    palette.setColor(QPalette.ColorRole.Button, QColor(45, 48, 58))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(220, 224, 230))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 80, 80))
    palette.setColor(QPalette.ColorRole.Link, QColor(66, 153, 225))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(44, 82, 130))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)
    app.setStyleSheet("""
        QGroupBox {
            border: 1px solid #2d3748; border-radius: 6px;
            margin-top: 14px; padding-top: 8px; font-weight: bold;
        }
        QGroupBox::title {
            subcontrol-origin: margin; subcontrol-position: top left;
            padding: 0 8px; color: #90cdf4;
        }
        QPushButton {
            background: #4a5568; color: white;
            padding: 6px 12px; border-radius: 4px; border: 1px solid #2d3748;
        }
        QPushButton:hover { background: #4299e1; }
        QPushButton:pressed { background: #2c5282; }
        QPushButton:disabled { background: #2d3748; color: #718096; }
        QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
            background: #1a202c; border: 1px solid #2d3748;
            border-radius: 4px; padding: 4px 6px; color: #e2e8f0;
        }
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus,
        QSpinBox:focus, QDoubleSpinBox:focus {
            border: 1px solid #4299e1;
        }
        QTableWidget {
            background: #1a202c; gridline-color: #2d3748;
            alternate-background-color: #1f2533;
        }
        QTableWidget::item:selected { background: #2c5282; color: white; }
        QHeaderView::section {
            background: #2d3748; color: white; padding: 6px;
            border: none; font-weight: bold;
        }
        QTabBar::tab {
            background: #2d3748; color: #e2e8f0;
            padding: 10px 18px; margin-right: 2px;
            border-top-left-radius: 4px; border-top-right-radius: 4px;
        }
        QTabBar::tab:selected { background: #2c5282; color: white; }
        QTabBar::tab:hover { background: #4a5568; }
    """)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    apply_dark_theme(app)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
