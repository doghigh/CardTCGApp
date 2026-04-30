import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart';
import '../models/card.dart';

class AppDatabase {
  static final AppDatabase instance = AppDatabase._();
  static Database? _db;

  AppDatabase._();

  Future<Database> get db async {
    _db ??= await _openDb();
    return _db!;
  }

  Future<Database> _openDb() async {
    final dbPath = await getDatabasesPath();
    final path = join(dbPath, 'cards.db');
    return openDatabase(
      path,
      version: 1,
      onCreate: (db, version) async {
        await db.execute('''
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
          )
        ''');
        await db.execute('''
          CREATE TABLE IF NOT EXISTS valuations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id INTEGER NOT NULL,
            source TEXT NOT NULL,
            value REAL NOT NULL,
            currency TEXT DEFAULT 'USD',
            url TEXT,
            fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE
          )
        ''');
        await db.execute('CREATE INDEX IF NOT EXISTS idx_cards_name ON cards(name)');
        await db.execute('CREATE INDEX IF NOT EXISTS idx_cards_set ON cards(set_name)');
        await db.execute('CREATE INDEX IF NOT EXISTS idx_valuations_card ON valuations(card_id)');
      },
    );
  }

  Future<int> addCard(CardModel card) async {
    final database = await db;
    return database.insert('cards', card.toMap());
  }

  Future<void> updateCard(int id, Map<String, dynamic> updates) async {
    final database = await db;
    updates['updated_at'] = DateTime.now().toIso8601String();
    await database.update('cards', updates, where: 'id = ?', whereArgs: [id]);
  }

  Future<void> deleteCard(int id) async {
    final database = await db;
    await database.delete('cards', where: 'id = ?', whereArgs: [id]);
  }

  Future<CardModel?> getCard(int id) async {
    final database = await db;
    final rows = await database.query('cards', where: 'id = ?', whereArgs: [id]);
    if (rows.isEmpty) return null;
    return CardModel.fromMap(rows.first);
  }

  Future<List<CardModel>> getAllCards({String? search}) async {
    final database = await db;
    List<Map<String, dynamic>> rows;
    if (search != null && search.isNotEmpty) {
      final q = '%$search%';
      rows = await database.query(
        'cards',
        where: 'name LIKE ? OR set_name LIKE ? OR game LIKE ?',
        whereArgs: [q, q, q],
        orderBy: 'updated_at DESC',
      );
    } else {
      rows = await database.query('cards', orderBy: 'updated_at DESC');
    }
    return rows.map(CardModel.fromMap).toList();
  }

  Future<void> addValuation(ValuationModel v) async {
    final database = await db;
    await database.insert('valuations', v.toMap());
  }

  Future<List<ValuationModel>> getValuations(int cardId) async {
    final database = await db;
    final rows = await database.query(
      'valuations',
      where: 'card_id = ?',
      whereArgs: [cardId],
      orderBy: 'fetched_at DESC',
    );
    return rows.map(ValuationModel.fromMap).toList();
  }

  Future<CollectionStats> getStats() async {
    final database = await db;
    final rows = await database.rawQuery('''
      SELECT
        COUNT(*) as total_cards,
        COALESCE(SUM(quantity), 0) as total_quantity,
        COALESCE(SUM(estimated_value * quantity), 0) as total_value,
        COALESCE(SUM(purchase_price * quantity), 0) as total_cost,
        COALESCE(AVG(condition_score), 0) as avg_condition
      FROM cards
    ''');
    if (rows.isEmpty) return const CollectionStats();
    return CollectionStats.fromMap(rows.first);
  }
}
