import 'dart:io';
import 'package:flutter/material.dart';
import 'package:share_plus/share_plus.dart';
import 'package:path_provider/path_provider.dart';
import 'package:path/path.dart' as p;
import 'package:csv/csv.dart';
import 'package:intl/intl.dart';
import '../db/database.dart';
import '../models/card.dart';
import 'detail_screen.dart';

class CollectionScreen extends StatefulWidget {
  const CollectionScreen({super.key});

  @override
  State<CollectionScreen> createState() => _CollectionScreenState();
}

class _CollectionScreenState extends State<CollectionScreen> {
  final _searchCtrl = TextEditingController();
  List<CardModel> _cards = [];
  CollectionStats _stats = const CollectionStats();
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
    _searchCtrl.addListener(() => _load(search: _searchCtrl.text.trim()));
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  Future<void> _load({String? search}) async {
    setState(() => _loading = true);
    final cards = await AppDatabase.instance.getAllCards(
        search: search?.isEmpty == true ? null : search);
    final stats = await AppDatabase.instance.getStats();
    if (mounted) {
      setState(() {
        _cards = cards;
        _stats = stats;
        _loading = false;
      });
    }
  }

  Future<void> _deleteCard(CardModel card) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete Card'),
        content:
            Text('Remove "${card.name}" from your collection? This cannot be undone.'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel')),
          TextButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Delete', style: TextStyle(color: Colors.red))),
        ],
      ),
    );
    if (confirmed == true) {
      await AppDatabase.instance.deleteCard(card.id!);
      _load(search: _searchCtrl.text.trim());
    }
  }

  Future<void> _exportCsv() async {
    final cards = await AppDatabase.instance.getAllCards();
    if (cards.isEmpty) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('No cards to export.')));
      return;
    }

    final rows = <List<dynamic>>[
      [
        'ID', 'Name', 'Set', 'Number', 'Rarity', 'Game', 'Year',
        'Language', 'Foil', 'Grade', 'Score', 'Quantity',
        'Estimated Value', 'Purchase Price', 'Total Value', 'Added',
      ],
      ...cards.map((c) {
        final qty = c.quantity;
        final val = c.estimatedValue;
        return [
          c.id, c.name, c.setName ?? '', c.cardNumber ?? '',
          c.rarity ?? '', c.game ?? '', c.year ?? '',
          c.language, c.foil ? 'Yes' : 'No', c.conditionGrade ?? '',
          c.conditionScore?.toStringAsFixed(1) ?? '', qty,
          val.toStringAsFixed(2), c.purchasePrice.toStringAsFixed(2),
          (val * qty).toStringAsFixed(2), c.createdAt ?? '',
        ];
      }),
    ];

    final csv = const ListToCsvConverter().convert(rows);
    final dir = await getTemporaryDirectory();
    final file = File(p.join(dir.path, 'collection.csv'));
    await file.writeAsString(csv);
    await Share.shareXFiles([XFile(file.path)], text: 'Trading Card Collection');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Collection'),
        actions: [
          IconButton(
            icon: const Icon(Icons.file_download_outlined),
            tooltip: 'Export CSV',
            onPressed: _exportCsv,
          ),
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => _load(search: _searchCtrl.text.trim()),
          ),
        ],
      ),
      body: Column(
        children: [
          _StatsBar(stats: _stats),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 10, 12, 6),
            child: TextField(
              controller: _searchCtrl,
              decoration: InputDecoration(
                hintText: 'Search name, set, or game…',
                prefixIcon: const Icon(Icons.search),
                suffixIcon: _searchCtrl.text.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear),
                        onPressed: () {
                          _searchCtrl.clear();
                          _load();
                        })
                    : null,
                isDense: true,
                border: const OutlineInputBorder(),
              ),
            ),
          ),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _cards.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.style_outlined,
                                size: 64, color: Colors.grey.shade700),
                            const SizedBox(height: 12),
                            Text(
                              _searchCtrl.text.isNotEmpty
                                  ? 'No cards match your search.'
                                  : 'No cards yet. Scan one!',
                              style: TextStyle(color: Colors.grey.shade500),
                            ),
                          ],
                        ),
                      )
                    : RefreshIndicator(
                        onRefresh: () => _load(search: _searchCtrl.text.trim()),
                        child: ListView.builder(
                          padding: const EdgeInsets.only(bottom: 16),
                          itemCount: _cards.length,
                          itemBuilder: (ctx, i) =>
                              _CardTile(card: _cards[i], onDelete: _deleteCard),
                        ),
                      ),
          ),
        ],
      ),
    );
  }
}

class _StatsBar extends StatelessWidget {
  final CollectionStats stats;
  const _StatsBar({required this.stats});

  @override
  Widget build(BuildContext context) {
    return Container(
      color: const Color(0xFF2c5282),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceAround,
        children: [
          _Stat(label: 'Cards', value: '${stats.totalCards}'),
          _Stat(label: 'Total Qty', value: '${stats.totalQuantity}'),
          _Stat(
              label: 'Value',
              value:
                  '\$${NumberFormat.compact().format(stats.totalValue)}'),
          _Stat(
              label: 'Net',
              value:
                  '${stats.netPosition >= 0 ? '+' : ''}\$${NumberFormat.compact().format(stats.netPosition)}',
              positive: stats.netPosition >= 0),
        ],
      ),
    );
  }
}

class _Stat extends StatelessWidget {
  final String label;
  final String value;
  final bool? positive;

  const _Stat({required this.label, required this.value, this.positive});

  @override
  Widget build(BuildContext context) {
    final color = positive == null
        ? Colors.white
        : positive!
            ? Colors.greenAccent
            : Colors.redAccent;
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(value,
            style:
                TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 15)),
        Text(label,
            style: TextStyle(color: Colors.white60, fontSize: 11)),
      ],
    );
  }
}

class _CardTile extends StatelessWidget {
  final CardModel card;
  final void Function(CardModel) onDelete;

  const _CardTile({required this.card, required this.onDelete});

  Color _gradeColor(double? score) {
    if (score == null) return Colors.grey;
    if (score >= 90) return Colors.green;
    if (score >= 70) return Colors.orange;
    return Colors.red;
  }

  @override
  Widget build(BuildContext context) {
    final score = card.conditionScore;
    final gradeColor = _gradeColor(score);

    return Dismissible(
      key: ValueKey(card.id),
      direction: DismissDirection.endToStart,
      background: Container(
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 20),
        color: Colors.red,
        child: const Icon(Icons.delete, color: Colors.white),
      ),
      confirmDismiss: (_) async {
        final confirmed = await showDialog<bool>(
          context: context,
          builder: (ctx) => AlertDialog(
            title: const Text('Delete Card'),
            content: Text('Remove "${card.name}"?'),
            actions: [
              TextButton(
                  onPressed: () => Navigator.pop(ctx, false),
                  child: const Text('Cancel')),
              TextButton(
                  onPressed: () => Navigator.pop(ctx, true),
                  child:
                      const Text('Delete', style: TextStyle(color: Colors.red))),
            ],
          ),
        );
        return confirmed ?? false;
      },
      onDismissed: (_) => onDelete(card),
      child: ListTile(
        onTap: () => Navigator.push(
          context,
          MaterialPageRoute(builder: (_) => DetailScreen(card: card)),
        ).then((_) => null),
        leading: _buildLeadingImage(),
        title: Text(card.name,
            style: const TextStyle(fontWeight: FontWeight.w600),
            maxLines: 1,
            overflow: TextOverflow.ellipsis),
        subtitle: Text(
          [
            if (card.setName != null) card.setName!,
            if (card.game != null) card.game!,
            if (card.cardNumber != null) '#${card.cardNumber}',
          ].join(' · '),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: TextStyle(color: Colors.grey.shade400, fontSize: 12),
        ),
        trailing: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text(
              '\$${(card.estimatedValue * card.quantity).toStringAsFixed(2)}',
              style: const TextStyle(fontWeight: FontWeight.bold),
            ),
            if (card.conditionGrade != null)
              Text(
                card.conditionGrade!,
                style: TextStyle(color: gradeColor, fontSize: 11),
              ),
            if (card.quantity > 1)
              Text('×${card.quantity}',
                  style: TextStyle(color: Colors.grey.shade500, fontSize: 11)),
          ],
        ),
      ),
    );
  }

  Widget _buildLeadingImage() {
    final path = card.frontScanPath;
    if (path != null && File(path).existsSync()) {
      return ClipRRect(
        borderRadius: BorderRadius.circular(4),
        child: Image.file(
          File(path),
          width: 40,
          height: 56,
          fit: BoxFit.cover,
        ),
      );
    }
    return Container(
      width: 40,
      height: 56,
      decoration: BoxDecoration(
        color: const Color(0xFF2d3748),
        borderRadius: BorderRadius.circular(4),
      ),
      child: const Icon(Icons.style, color: Colors.grey, size: 20),
    );
  }
}
