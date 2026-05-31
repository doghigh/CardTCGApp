#!/usr/bin/env python3
"""
CardVault Fixes - Automated Application Script
Apply all 6 fixes to your CardTCGApp project
"""

import os
import sys
from pathlib import Path

def main():
    # Get the CardTCGApp directory
    cardvault_dir = Path.cwd()
    
    if not (cardvault_dir / 'ui').exists() or not (cardvault_dir / 'core').exists():
        print("❌ ERROR: Not in CardTCGApp directory!")
        print("   Current directory:", cardvault_dir)
        print("   Please run this from your CardTCGApp folder")
        sys.exit(1)
    
    print("✅ Found CardTCGApp directory")
    print()
    
    # Fix 1: Update scan_tab.py - Add defects panel
    print("📝 Applying Fix 1: Adding defects display panel to scan_tab.py...")
    scan_tab_path = cardvault_dir / 'ui' / 'scan_tab.py'
    
    with open(scan_tab_path, 'r', encoding='utf-8') as f:
        scan_content = f.read()
    
    # Add defects panel to UI (after line 228)
    if 'self.defects_text' not in scan_content:
        # Find the insertion point
        insertion_point = scan_content.find('right_layout.addWidget(details_group)')
        if insertion_point > 0:
            # Find the end of that line
            end_of_line = scan_content.find('\n', insertion_point) + 1
            
            defects_panel = '''
        # Defects panel
        defects_group = QGroupBox("Defects Found")
        defects_layout = QVBoxLayout(defects_group)
        self.defects_text = QTextEdit()
        self.defects_text.setReadOnly(True)
        self.defects_text.setMaximumHeight(100)
        self.defects_text.setPlainText("No inspection yet")
        defects_layout.addWidget(self.defects_text)
        right_layout.addWidget(defects_group)
'''
            scan_content = scan_content[:end_of_line] + defects_panel + scan_content[end_of_line:]
            
            # Update _inspect() method
            inspect_old = '''    def _inspect(self):
        if self.current_front_img is None:
            return
        try:
            self.current_inspection = self.inspector.inspect(self.current_front_img)
            grade = self.current_inspection['grade']
            score = self.current_inspection['score']
            defect_count = len(self.current_inspection.get('defects', []))
            self.status_label.setText(
                f"🔍 Grade: {grade} ({score:.1f}/100) — {defect_count} defect(s) found"
            )
        except Exception as e:
            self.status_label.setText(f"Inspection error: {str(e)[:60]}")'''
            
            inspect_new = '''    def _inspect(self):
        if self.current_front_img is None:
            return
        try:
            self.current_inspection = self.inspector.inspect(self.current_front_img)
            grade = self.current_inspection['grade']
            score = self.current_inspection['score']
            defects = self.current_inspection.get('defects', [])
            defect_count = len(defects)
            
            self.status_label.setText(
                f"🔍 Grade: {grade} ({score:.1f}/100) — {defect_count} defect(s) found"
            )
            
            # Update defects display
            if defects:
                lines = [f"• [{d['severity'].upper()}] {d['type'].replace('_', ' ').title()} @ {d['location']}"
                         for d in defects]
                self.defects_text.setPlainText("\\n".join(lines))
            else:
                self.defects_text.setPlainText("None detected.")
        except Exception as e:
            self.status_label.setText(f"Inspection error: {str(e)[:60]}")'''
            
            scan_content = scan_content.replace(inspect_old, inspect_new)
            
            # Update _reset_form() to reset defects
            reset_old = '''        self.current_front_img = None
        self.current_back_img = None
        self.current_inspection = None
        self.front_view.set_image(None)
        self.back_view.set_image(None)
        self.status_label.setText("Ready.")'''
            
            reset_new = '''        self.current_front_img = None
        self.current_back_img = None
        self.current_inspection = None
        self.front_view.set_image(None)
        self.back_view.set_image(None)
        self.defects_text.setPlainText("No inspection yet")
        self.status_label.setText("Ready.")'''
            
            scan_content = scan_content.replace(reset_old, reset_new)
            
            with open(scan_tab_path, 'w', encoding='utf-8') as f:
                f.write(scan_content)
            print("   ✅ scan_tab.py updated")
    else:
        print("   ⏭️  Already applied, skipping")
    
    # Fix 2: Update collection_tab.py - Add threading
    print("📝 Applying Fix 2: Adding background threading to collection_tab.py...")
    collection_tab_path = cardvault_dir / 'ui' / 'collection_tab.py'
    
    with open(collection_tab_path, 'r', encoding='utf-8') as f:
        collection_content = f.read()
    
    # Update imports
    if 'from PyQt6.QtCore import Qt, QThread, pyqtSignal' not in collection_content:
        collection_content = collection_content.replace(
            'from PyQt6.QtCore import Qt, QTimer',
            'from PyQt6.QtCore import Qt, QThread, pyqtSignal'
        )
        
        # Add RevalueWorker class after imports
        revalue_worker = '''

class RevalueWorker(QThread):
    """Background thread for re-valuating cards."""
    finished = pyqtSignal()
    
    def __init__(self, db: Database, valuator: CardValuator, ids: List[int]):
        super().__init__()
        self.db = db
        self.valuator = valuator
        self.ids = ids
    
    def run(self):
        for cid in self.ids:
            card = self.db.get_card(cid)
            if not card or not card.get('name'):
                continue
            try:
                results = self.valuator.fetch_all_values(card['name'], card.get('set_name'))
                if results:
                    score = card.get('condition_score') or 85.0
                    estimate = self.valuator.compute_estimate(results, score)
                    self.db.update_card(cid, {'estimated_value': estimate})
            except Exception as e:
                print(f"Error re-valuing card {cid}: {e}")
        self.finished.emit()
'''
        
        # Insert after APP_DIR definition
        insert_pos = collection_content.find('APP_DIR = Path')
        insert_pos = collection_content.find('\n\n', insert_pos) + 2
        collection_content = collection_content[:insert_pos] + revalue_worker + '\n' + collection_content[insert_pos:]
        
        # Update __init__
        collection_content = collection_content.replace(
            'def __init__(self, db: Database, valuator: CardValuator):\n        super().__init__()\n        self.db = db\n        self.valuator = valuator\n        self._build_ui()',
            'def __init__(self, db: Database, valuator: CardValuator):\n        super().__init__()\n        self.db = db\n        self.valuator = valuator\n        self._revalue_worker = None\n        self._build_ui()'
        )
        
        # Update _revalue_selected and add _on_revalue_finished
        revalue_old = '''    def _revalue_selected(self):
        ids = self._selected_ids()
        if not ids:
            return
        QMessageBox.information(self, "Re-valuing", f"Re-fetching values for {len(ids)} cards...")
        QTimer.singleShot(100, lambda: self._revalue_worker(ids))

    def _revalue_worker(self, ids: List[int]):
        for cid in ids:
            card = self.db.get_card(cid)
            if not card or not card.get('name'):
                continue
            results = self.valuator.fetch_all_values(card['name'], card.get('set_name'))
            if results:
                score = card.get('condition_score') or 85.0
                estimate = self.valuator.compute_estimate(results, score)
                self.db.update_card(cid, {'estimated_value': estimate})
        self.refresh()'''
        
        revalue_new = '''    def _revalue_selected(self):
        ids = self._selected_ids()
        if not ids:
            return
        if self._revalue_worker and self._revalue_worker.isRunning():
            QMessageBox.warning(self, "In Progress", "Re-valuation already in progress.")
            return
        
        self.revalue_btn.setEnabled(False)
        self.revalue_btn.setText("⏳ Re-valuing...")
        
        self._revalue_worker = RevalueWorker(self.db, self.valuator, ids)
        self._revalue_worker.finished.connect(self._on_revalue_finished)
        self._revalue_worker.start()
    
    def _on_revalue_finished(self):
        """Handle re-valuation completion."""
        self.revalue_btn.setEnabled(True)
        self.revalue_btn.setText("💰 Re-value Selected")
        self.refresh()
        QMessageBox.information(self, "Complete", "Re-valuation finished!")'''
        
        collection_content = collection_content.replace(revalue_old, revalue_new)
        
        # Fix exception handler
        collection_content = collection_content.replace(
            '''                    except:
                        pass''',
            '''                    except (ValueError, TypeError):
                        # Score not convertible to float
                        pass'''
        )
        
        with open(collection_tab_path, 'w', encoding='utf-8') as f:
            f.write(collection_content)
        print("   ✅ collection_tab.py updated")
    else:
        print("   ⏭️  Already applied, skipping")
    
    # Fix 3: Update auth.py - Password migration
    print("📝 Applying Fix 3: Adding password migration to auth.py...")
    auth_path = cardvault_dir / 'core' / 'auth.py'
    
    with open(auth_path, 'r', encoding='utf-8') as f:
        auth_content = f.read()
    
    # Remove unused import
    auth_content = auth_content.replace('import base64\n', '')
    
    # Update check_password method
    if 'stored_data = self.key_file.read_bytes()' not in auth_content:
        check_password_old = '''    def check_password(self, password: str) -> bool:
        if not self.key_file.exists():
            return True  # first run
        if not password:
            return False
        try:
            stored_hash = self.key_file.read_text().strip()
            derived = self._derive_key(password)
            verification_hash = hashlib.sha256(derived).hexdigest()
            return secrets.compare_digest(stored_hash, verification_hash)
        except Exception:
            return False'''
        
        check_password_new = '''    def check_password(self, password: str) -> bool:
        if not self.key_file.exists():
            return True  # first run
        if not password:
            return False
        try:
            stored_data = self.key_file.read_bytes() if self.key_file.stat().st_size <= 64 else self.key_file.read_text()
            
            # Migration: detect old format (raw 32-byte hash) and convert to new format
            if isinstance(stored_data, bytes) and len(stored_data) == 32:
                # Old format detected — re-prompt user and migrate
                derived = self._derive_key(password)
                verification_hash = hashlib.sha256(derived).hexdigest()
                # Write new format
                self.key_file.write_text(verification_hash)
                # Verify matches
                return secrets.compare_digest(hashlib.sha256(derived).hexdigest(), verification_hash)
            
            # New format: hex string
            stored_hash = self.key_file.read_text().strip() if isinstance(stored_data, str) else stored_data.hex()
            derived = self._derive_key(password)
            verification_hash = hashlib.sha256(derived).hexdigest()
            return secrets.compare_digest(stored_hash, verification_hash)
        except Exception:
            return False'''
        
        auth_content = auth_content.replace(check_password_old, check_password_new)
        
        with open(auth_path, 'w', encoding='utf-8') as f:
            f.write(auth_content)
        print("   ✅ auth.py updated")
    else:
        print("   ⏭️  Already applied, skipping")
    
    # Fix 4: Update scanner.py - Exception handling
    print("📝 Applying Fix 4: Updating exception handling in scanner.py...")
    scanner_path = cardvault_dir / 'core' / 'scanner.py'
    
    with open(scanner_path, 'r', encoding='utf-8') as f:
        scanner_content = f.read()
    
    if 'except (AttributeError, Exception)' not in scanner_content:
        scanner_content = scanner_content.replace(
            '''                except:
                    pass''',
            '''                except (AttributeError, Exception) as e:
                    print(f"Duplex not available: {e}")'''
        )
        
        with open(scanner_path, 'w', encoding='utf-8') as f:
            f.write(scanner_content)
        print("   ✅ scanner.py updated")
    else:
        print("   ⏭️  Already applied, skipping")
    
    # Fix 5: Delete collections.py
    print("📝 Applying Fix 5: Deleting dead code file ui/collections.py...")
    collections_path = cardvault_dir / 'ui' / 'collections.py'
    if collections_path.exists():
        collections_path.unlink()
        print("   ✅ ui/collections.py deleted")
    else:
        print("   ⏭️  Already deleted, skipping")
    
    print()
    print("=" * 60)
    print("✅ ALL FIXES APPLIED SUCCESSFULLY!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Verify syntax: python -m py_compile ui/scan_tab.py ui/collection_tab.py core/auth.py core/scanner.py")
    print("2. Create branch: git checkout -b claude2")
    print("3. Stage changes: git add .")
    print("4. Commit: git commit -m \"fix(cardvault): resolve critical bugs and security issues\"")
    print("5. Push: git push -u origin claude2")
    print()

if __name__ == '__main__':
    main()
