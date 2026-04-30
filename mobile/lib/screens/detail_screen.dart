import 'dart:io';
import 'package:flutter/material.dart';
import '../db/database.dart';
import '../models/card.dart';
import '../services/valuator.dart';

class DetailScreen extends StatefulWidget {
  final CardModel card;
  const DetailScreen({super.key, required this.card});

  @override
  State<DetailScreen> createState() => _DetailScreenState();
}

class _DetailScreenState extends State<DetailScreen> {
  late CardModel _card;
  List<ValuationModel> _valuations = [];
  bool _fetchingValue = false;
  final _valuator = CardValuator();

  @override
  void initState() {
    super.initState();
    _card = widget.card;
    _loadValuations();
  }

  Future<void> _loadValuations() async {
    if (_card.id == null) return;
    final vals = await AppDatabase.instance.getValuations(_card.id!);
    if (mounted) setState(() => _valuations = vals);
  }

  Future<void> _refreshValue() async {
    setState(() => _fetchingValue = true);
    try {
      final results = await _valuator.fetchAll(
        _card.name,
        setName: _card.setName,
      );
      if (results.isEmpty) {
        _snack('No prices found.');
        return;
      }
      final estimate =
          _valuator.computeEstimate(results, _card.conditionScore ?? 85.0);
      await AppDatabase.instance.updateCard(_card.id!, {
        'estimated_value': estimate,
      });
      for (final v in results) {
        await AppDatabase.instance.addValuation(ValuationModel(
          cardId: _card.id!,
          source: v.source,
          value: v.value,
          url: v.url,
        ));
      }
      final updated = await AppDatabase.instance.getCard(_card.id!);
      if (updated != null && mounted) {
        setState(() => _card = updated);
      }
      await _loadValuations();
      _snack('Updated to \$${estimate.toStringAsFixed(2)}');
    } catch (e) {
      _snack('Error: $e');
    } finally {
      if (mounted) setState(() => _fetchingValue = false);
    }
  }

  void _snack(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(msg), duration: const Duration(seconds: 3)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_card.name, overflow: TextOverflow.ellipsis),
        actions: [
          IconButton(
            icon: _fetchingValue
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(
                        color: Colors.white, strokeWidth: 2))
                : const Icon(Icons.currency_exchange),
            tooltip: 'Refresh value',
            onPressed: _fetchingValue ? null : _refreshValue,
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _buildImageRow(),
            const SizedBox(height: 16),
            _buildInfoCard(),
            const SizedBox(height: 12),
            _buildConditionCard(),
            const SizedBox(height: 12),
            _buildFinancialCard(),
            const SizedBox(height: 12),
            if (_valuations.isNotEmpty) _buildValuationsCard(),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }

  Widget _buildImageRow() {
    return Row(
      children: [
        Expanded(
            child:
                _buildImagePanel('Front', _card.frontScanPath, Icons.looks_one)),
        const SizedBox(width: 12),
        Expanded(
            child:
                _buildImagePanel('Back', _card.backScanPath, Icons.looks_two)),
      ],
    );
  }

  Widget _buildImagePanel(String label, String? path, IconData placeholder) {
    return Column(
      children: [
        Text(label,
            style:
                const TextStyle(fontWeight: FontWeight.bold, fontSize: 12)),
        const SizedBox(height: 4),
        Container(
          height: 180,
          decoration: BoxDecoration(
            color: const Color(0xFF1a202c),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: const Color(0xFF2d3748)),
          ),
          child: path != null && File(path).existsSync()
              ? ClipRRect(
                  borderRadius: BorderRadius.circular(7),
                  child: GestureDetector(
                    onTap: () => _showFullImage(context, path),
                    child: Image.file(File(path), fit: BoxFit.contain),
                  ),
                )
              : Center(
                  child: Icon(placeholder,
                      color: Colors.grey.shade700, size: 40)),
        ),
      ],
    );
  }

  void _showFullImage(BuildContext context, String path) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => Scaffold(
          backgroundColor: Colors.black,
          appBar: AppBar(backgroundColor: Colors.black),
          body: Center(
            child: InteractiveViewer(
              child: Image.file(File(path)),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildInfoCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionHeader(Icons.info_outline, 'Card Info'),
            const Divider(height: 12),
            _row('Name', _card.name),
            if (_card.setName != null) _row('Set', _card.setName!),
            if (_card.cardNumber != null) _row('Card #', _card.cardNumber!),
            if (_card.rarity != null) _row('Rarity', _card.rarity!),
            if (_card.game != null) _row('Game', _card.game!),
            if (_card.year != null) _row('Year', '${_card.year}'),
            _row('Language', _card.language),
            _row('Foil', _card.foil ? 'Yes' : 'No'),
            _row('Quantity', '${_card.quantity}'),
            if (_card.notes != null && _card.notes!.isNotEmpty)
              _row('Notes', _card.notes!),
            if (_card.createdAt != null)
              _row('Added', _card.createdAt!.substring(0, 10)),
          ],
        ),
      ),
    );
  }

  Widget _buildConditionCard() {
    final score = _card.conditionScore;
    final color = score == null
        ? Colors.grey
        : score >= 90
            ? Colors.green
            : score >= 70
                ? Colors.orange
                : Colors.red;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionHeader(Icons.fact_check_outlined, 'Condition'),
            const Divider(height: 12),
            if (_card.conditionGrade != null)
              Row(
                children: [
                  Text(
                    _card.conditionGrade!,
                    style: TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.bold,
                        color: color),
                  ),
                  const SizedBox(width: 12),
                  if (score != null)
                    Text('${score.toStringAsFixed(1)}/100',
                        style: TextStyle(color: color, fontSize: 15)),
                ],
              )
            else
              const Text('Not inspected',
                  style: TextStyle(color: Colors.grey)),
            if (_card.defects.isNotEmpty) ...[
              const SizedBox(height: 10),
              const Text('Defects',
                  style: TextStyle(
                      fontWeight: FontWeight.w600, fontSize: 13)),
              const SizedBox(height: 6),
              ..._card.defects.map((d) => _DefectRow(defect: d)),
            ] else if (_card.conditionGrade != null)
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Text('No defects detected',
                    style: TextStyle(
                        color: Colors.green.shade400, fontSize: 13)),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildFinancialCard() {
    final net = _card.estimatedValue - _card.purchasePrice;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionHeader(Icons.attach_money, 'Financial'),
            const Divider(height: 12),
            _row('Est. Value (unit)',
                '\$${_card.estimatedValue.toStringAsFixed(2)}'),
            _row('Total Value',
                '\$${(_card.estimatedValue * _card.quantity).toStringAsFixed(2)}'),
            _row('Purchase Price',
                '\$${_card.purchasePrice.toStringAsFixed(2)}'),
            Row(
              children: [
                const Expanded(
                    child: Text('Net / card',
                        style: TextStyle(fontSize: 13, color: Colors.grey))),
                Text(
                  '${net >= 0 ? '+' : ''}\$${net.toStringAsFixed(2)}',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 13,
                    color: net >= 0 ? Colors.green : Colors.red,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildValuationsCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionHeader(Icons.history, 'Price History'),
            const Divider(height: 12),
            ..._valuations.take(10).map((v) => Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Row(
                    children: [
                      Expanded(
                          child: Text(v.source,
                              style: const TextStyle(fontSize: 13))),
                      Text(
                        '\$${v.value.toStringAsFixed(2)}',
                        style: const TextStyle(fontWeight: FontWeight.w600),
                      ),
                      const SizedBox(width: 8),
                      if (v.fetchedAt != null)
                        Text(
                          v.fetchedAt!.substring(0, 10),
                          style: TextStyle(
                              color: Colors.grey.shade500, fontSize: 11),
                        ),
                    ],
                  ),
                )),
          ],
        ),
      ),
    );
  }

  Widget _sectionHeader(IconData icon, String title) => Row(
        children: [
          Icon(icon, size: 18),
          const SizedBox(width: 8),
          Text(title,
              style:
                  const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
        ],
      );

  Widget _row(String label, String value) => Padding(
        padding: const EdgeInsets.only(bottom: 4),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(
              width: 110,
              child: Text(label,
                  style: TextStyle(fontSize: 13, color: Colors.grey.shade400)),
            ),
            Expanded(
              child: Text(value,
                  style: const TextStyle(fontSize: 13),
                  overflow: TextOverflow.ellipsis,
                  maxLines: 3),
            ),
          ],
        ),
      );
}

class _DefectRow extends StatelessWidget {
  final Defect defect;
  const _DefectRow({required this.defect});

  Color get _color => switch (defect.severity) {
        'severe' => Colors.red,
        'moderate' => Colors.orange,
        _ => Colors.amber,
      };

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(
        children: [
          Container(
            width: 8,
            height: 8,
            margin: const EdgeInsets.only(right: 8),
            decoration: BoxDecoration(color: _color, shape: BoxShape.circle),
          ),
          Expanded(
            child: Text(
              '${defect.displayType} @ ${defect.location}',
              style: const TextStyle(fontSize: 12),
            ),
          ),
          Text(
            defect.severity.toUpperCase(),
            style: TextStyle(
                color: _color, fontSize: 10, fontWeight: FontWeight.bold),
          ),
        ],
      ),
    );
  }
}
