import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:intl/intl.dart';
import 'package:path_provider/path_provider.dart';
import 'package:path/path.dart' as p;
import '../db/database.dart';
import '../models/card.dart';
import '../services/inspector.dart';
import '../services/valuator.dart';

class ScanScreen extends StatefulWidget {
  const ScanScreen({super.key});

  @override
  State<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends State<ScanScreen> {
  final _picker = ImagePicker();
  final _inspector = CardInspector();
  final _valuator = CardValuator();

  // Images
  File? _frontFile;
  File? _backFile;
  Uint8List? _frontBytes;
  Uint8List? _backBytes;

  // Inspection
  InspectionResult? _inspection;
  bool _inspecting = false;

  // Valuation
  List<ValuationResult> _valuations = [];
  bool _fetchingValue = false;

  // Saving
  bool _saving = false;

  // Form
  final _nameCtrl = TextEditingController();
  final _setCtrl = TextEditingController();
  final _numberCtrl = TextEditingController();
  final _rarityCtrl = TextEditingController();
  final _notesCtrl = TextEditingController();
  String _game = 'Pokémon';
  bool _foil = false;
  int _quantity = 1;
  double _purchasePrice = 0.0;
  int _year = DateTime.now().year;

  static const _games = [
    'Magic: The Gathering',
    'Pokémon',
    'Yu-Gi-Oh!',
    'One Piece',
    'Lorcana',
    'Flesh and Blood',
    'Sports',
    'Other',
  ];

  @override
  void dispose() {
    _nameCtrl.dispose();
    _setCtrl.dispose();
    _numberCtrl.dispose();
    _rarityCtrl.dispose();
    _notesCtrl.dispose();
    super.dispose();
  }

  Future<void> _pickImage(String side, ImageSource source) async {
    final xfile = await _picker.pickImage(
      source: source,
      imageQuality: 90,
      preferredCameraDevice: CameraDevice.rear,
    );
    if (xfile == null) return;

    final bytes = await xfile.readAsBytes();
    final file = File(xfile.path);

    setState(() {
      if (side == 'front') {
        _frontFile = file;
        _frontBytes = bytes;
        _inspection = null;
      } else {
        _backFile = file;
        _backBytes = bytes;
      }
    });

    if (side == 'front') {
      await _runInspection();
    }
  }

  Future<void> _runInspection() async {
    if (_frontBytes == null) return;
    setState(() => _inspecting = true);
    try {
      final result = await _inspector.inspect(_frontBytes!);
      setState(() => _inspection = result);
    } catch (e) {
      _showSnack('Inspection failed: $e');
    } finally {
      setState(() => _inspecting = false);
    }
  }

  Future<void> _fetchValue() async {
    final name = _nameCtrl.text.trim();
    if (name.isEmpty) {
      _showSnack('Enter a card name first.');
      return;
    }
    setState(() {
      _fetchingValue = true;
      _valuations = [];
    });
    try {
      final results = await _valuator.fetchAll(
        name,
        setName: _setCtrl.text.trim().isEmpty ? null : _setCtrl.text.trim(),
      );
      setState(() => _valuations = results);
      if (results.isEmpty) {
        _showSnack('No prices found online.');
      } else {
        _showSnack('Found ${results.length} price source(s).');
      }
    } catch (e) {
      _showSnack('Valuation error: $e');
    } finally {
      setState(() => _fetchingValue = false);
    }
  }

  Future<void> _saveCard() async {
    if (_nameCtrl.text.trim().isEmpty) {
      _showSnack('Card name is required.');
      return;
    }
    setState(() => _saving = true);

    try {
      final docsDir = await getApplicationDocumentsDirectory();
      final scansDir = Directory(p.join(docsDir.path, 'scans'));
      await scansDir.create(recursive: true);
      final ts = DateFormat('yyyyMMdd_HHmmss').format(DateTime.now());

      String? frontPath;
      String? backPath;

      if (_frontFile != null) {
        frontPath = p.join(scansDir.path, 'card_${ts}_front.jpg');
        await _frontFile!.copy(frontPath);
      }
      if (_backFile != null) {
        backPath = p.join(scansDir.path, 'card_${ts}_back.jpg');
        await _backFile!.copy(backPath);
      }

      final condScore = _inspection?.score;
      final estimate = _valuations.isNotEmpty
          ? _valuator.computeEstimate(_valuations, condScore ?? 85.0)
          : 0.0;

      final card = CardModel(
        name: _nameCtrl.text.trim(),
        setName: _setCtrl.text.trim().isEmpty ? null : _setCtrl.text.trim(),
        cardNumber:
            _numberCtrl.text.trim().isEmpty ? null : _numberCtrl.text.trim(),
        rarity: _rarityCtrl.text.trim().isEmpty ? null : _rarityCtrl.text.trim(),
        game: _game,
        year: _year,
        language: 'English',
        foil: _foil,
        frontScanPath: frontPath,
        backScanPath: backPath,
        conditionGrade: _inspection?.grade,
        conditionScore: condScore,
        defects: _inspection?.defects ?? [],
        estimatedValue: estimate,
        purchasePrice: _purchasePrice,
        purchaseDate: DateFormat('yyyy-MM-dd').format(DateTime.now()),
        notes: _notesCtrl.text.trim().isEmpty ? null : _notesCtrl.text.trim(),
        quantity: _quantity,
      );

      final cardId = await AppDatabase.instance.addCard(card);

      for (final v in _valuations) {
        await AppDatabase.instance.addValuation(ValuationModel(
          cardId: cardId,
          source: v.source,
          value: v.value,
          url: v.url,
        ));
      }

      if (mounted) {
        _showSnack('Saved "${card.name}" — est. \$${estimate.toStringAsFixed(2)}');
        _reset();
      }
    } catch (e) {
      _showSnack('Save failed: $e');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  void _reset() {
    setState(() {
      _frontFile = null;
      _backFile = null;
      _frontBytes = null;
      _backBytes = null;
      _inspection = null;
      _valuations = [];
    });
    _nameCtrl.clear();
    _setCtrl.clear();
    _numberCtrl.clear();
    _rarityCtrl.clear();
    _notesCtrl.clear();
    setState(() {
      _game = 'Pokémon';
      _foil = false;
      _quantity = 1;
      _purchasePrice = 0.0;
      _year = DateTime.now().year;
    });
  }

  void _showSnack(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(msg), duration: const Duration(seconds: 3)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Scan Card'),
        actions: [
          if (_frontFile != null || _backFile != null)
            IconButton(
              icon: const Icon(Icons.refresh),
              tooltip: 'Reset',
              onPressed: _reset,
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
            if (_inspecting)
              const _StatusCard(
                icon: Icons.search,
                color: Colors.blue,
                text: 'Analyzing card...',
                loading: true,
              ),
            if (_inspection != null && !_inspecting) _buildInspectionCard(),
            const SizedBox(height: 16),
            _buildDetailsForm(),
            const SizedBox(height: 16),
            _buildValuationSection(),
            const SizedBox(height: 24),
            _buildSaveButton(),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }

  Widget _buildImageRow() {
    return Row(
      children: [
        Expanded(child: _buildImagePanel('Front', _frontFile, 'front')),
        const SizedBox(width: 12),
        Expanded(child: _buildImagePanel('Back', _backFile, 'back')),
      ],
    );
  }

  Widget _buildImagePanel(String label, File? file, String side) {
    return Column(
      children: [
        Text(label, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
        const SizedBox(height: 6),
        GestureDetector(
          onTap: () => _showPickerDialog(side),
          child: Container(
            height: 200,
            decoration: BoxDecoration(
              color: const Color(0xFF1a202c),
              border: Border.all(
                color: file != null ? Colors.blue.shade400 : const Color(0xFF2d3748),
                width: 2,
              ),
              borderRadius: BorderRadius.circular(8),
            ),
            child: file != null
                ? ClipRRect(
                    borderRadius: BorderRadius.circular(6),
                    child: Image.file(file, fit: BoxFit.contain),
                  )
                : Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.add_a_photo_outlined,
                          color: Colors.grey.shade600, size: 36),
                      const SizedBox(height: 8),
                      Text('Tap to add',
                          style: TextStyle(color: Colors.grey.shade600, fontSize: 12)),
                    ],
                  ),
          ),
        ),
        const SizedBox(height: 6),
        Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                icon: const Icon(Icons.camera_alt, size: 14),
                label: const Text('Camera', style: TextStyle(fontSize: 11)),
                onPressed: () => _pickImage(side, ImageSource.camera),
                style: OutlinedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                ),
              ),
            ),
            const SizedBox(width: 4),
            Expanded(
              child: OutlinedButton.icon(
                icon: const Icon(Icons.photo_library, size: 14),
                label: const Text('Gallery', style: TextStyle(fontSize: 11)),
                onPressed: () => _pickImage(side, ImageSource.gallery),
                style: OutlinedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }

  void _showPickerDialog(String side) {
    showModalBottomSheet(
      context: context,
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.camera_alt),
              title: const Text('Camera'),
              onTap: () {
                Navigator.pop(ctx);
                _pickImage(side, ImageSource.camera);
              },
            ),
            ListTile(
              leading: const Icon(Icons.photo_library),
              title: const Text('Gallery'),
              onTap: () {
                Navigator.pop(ctx);
                _pickImage(side, ImageSource.gallery);
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildInspectionCard() {
    final ins = _inspection!;
    final color = ins.score >= 90
        ? Colors.green
        : ins.score >= 70
            ? Colors.orange
            : Colors.red;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.fact_check, size: 18),
                const SizedBox(width: 8),
                const Text('Condition',
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
                const Spacer(),
                TextButton(
                  onPressed: _runInspection,
                  child: const Text('Re-inspect'),
                ),
              ],
            ),
            const Divider(height: 12),
            Row(
              children: [
                Text(ins.grade,
                    style: TextStyle(
                        fontSize: 22, fontWeight: FontWeight.bold, color: color)),
                const Spacer(),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text('${ins.score}/100',
                        style: TextStyle(color: color, fontWeight: FontWeight.w600)),
                    Text('Centering: ${ins.centeringScore}/100',
                        style: TextStyle(color: Colors.grey.shade400, fontSize: 12)),
                  ],
                ),
              ],
            ),
            if (ins.defects.isNotEmpty) ...[
              const SizedBox(height: 8),
              ...ins.defects.map((d) => _DefectChip(defect: d)),
            ] else
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text('No defects detected',
                    style: TextStyle(color: Colors.green.shade400, fontSize: 13)),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildDetailsForm() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.edit_note, size: 18),
                SizedBox(width: 8),
                Text('Card Details',
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
              ],
            ),
            const Divider(height: 16),
            _field('Name *', _nameCtrl),
            _field('Set', _setCtrl),
            _field('Card #', _numberCtrl),
            _field('Rarity', _rarityCtrl),
            const SizedBox(height: 10),
            DropdownButtonFormField<String>(
              value: _game,
              decoration: _inputDeco('Game'),
              items: _games
                  .map((g) => DropdownMenuItem(value: g, child: Text(g)))
                  .toList(),
              onChanged: (v) => setState(() => _game = v!),
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(
                  child: TextFormField(
                    decoration: _inputDeco('Year'),
                    keyboardType: TextInputType.number,
                    initialValue: _year.toString(),
                    onChanged: (v) => _year = int.tryParse(v) ?? _year,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: TextFormField(
                    decoration: _inputDeco('Qty'),
                    keyboardType: TextInputType.number,
                    initialValue: '1',
                    onChanged: (v) => _quantity = int.tryParse(v) ?? 1,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: TextFormField(
                    decoration: _inputDeco('Buy price \$'),
                    keyboardType:
                        const TextInputType.numberWithOptions(decimal: true),
                    initialValue: '0.00',
                    onChanged: (v) =>
                        _purchasePrice = double.tryParse(v) ?? 0.0,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Foil / Holographic'),
              value: _foil,
              onChanged: (v) => setState(() => _foil = v),
            ),
            _field('Notes', _notesCtrl, maxLines: 2),
          ],
        ),
      ),
    );
  }

  Widget _buildValuationSection() {
    final estimate = _valuations.isNotEmpty
        ? _valuator.computeEstimate(
            _valuations, _inspection?.score ?? 85.0)
        : null;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.attach_money, size: 18),
                const SizedBox(width: 8),
                const Text('Valuation',
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
                const Spacer(),
                ElevatedButton.icon(
                  icon: _fetchingValue
                      ? const SizedBox(
                          width: 14,
                          height: 14,
                          child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.search, size: 16),
                  label: const Text('Fetch Prices'),
                  onPressed: _fetchingValue ? null : _fetchValue,
                ),
              ],
            ),
            if (estimate != null) ...[
              const Divider(height: 16),
              Text('\$${estimate.toStringAsFixed(2)}',
                  style: const TextStyle(
                      fontSize: 28,
                      fontWeight: FontWeight.bold,
                      color: Color(0xFF38a169))),
              Text(
                'Condition-adjusted from ${_valuations.length} source(s)',
                style: TextStyle(color: Colors.grey.shade400, fontSize: 12),
              ),
              const SizedBox(height: 8),
              ..._valuations.map((v) => Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Row(
                      children: [
                        Expanded(
                            child: Text(v.source,
                                style: const TextStyle(fontSize: 13))),
                        Text('\$${v.value.toStringAsFixed(2)}',
                            style: const TextStyle(
                                fontWeight: FontWeight.w600, fontSize: 13)),
                      ],
                    ),
                  )),
            ] else if (!_fetchingValue)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text('Tap Fetch Prices after entering a card name.',
                    style: TextStyle(color: Colors.grey.shade500, fontSize: 13)),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildSaveButton() {
    return SizedBox(
      height: 52,
      child: ElevatedButton.icon(
        icon: _saving
            ? const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(
                    color: Colors.white, strokeWidth: 2.5))
            : const Icon(Icons.save),
        label: const Text('Save to Collection',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
        onPressed: _saving ? null : _saveCard,
        style: ElevatedButton.styleFrom(
          backgroundColor: const Color(0xFF2c5282),
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        ),
      ),
    );
  }

  Widget _field(String label, TextEditingController ctrl, {int maxLines = 1}) =>
      Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: TextField(
          controller: ctrl,
          maxLines: maxLines,
          decoration: _inputDeco(label),
          textCapitalization: TextCapitalization.words,
        ),
      );

  InputDecoration _inputDeco(String label) => InputDecoration(
        labelText: label,
        isDense: true,
        border: const OutlineInputBorder(),
      );
}

class _DefectChip extends StatelessWidget {
  final Defect defect;
  const _DefectChip({required this.defect});

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
            decoration: BoxDecoration(color: _color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              '${defect.displayType} @ ${defect.location}',
              style: const TextStyle(fontSize: 12),
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(
              color: _color.withOpacity(0.2),
              borderRadius: BorderRadius.circular(4),
            ),
            child: Text(
              defect.severity.toUpperCase(),
              style: TextStyle(
                  color: _color, fontSize: 10, fontWeight: FontWeight.bold),
            ),
          ),
        ],
      ),
    );
  }
}

class _StatusCard extends StatelessWidget {
  final IconData icon;
  final Color color;
  final String text;
  final bool loading;

  const _StatusCard({
    required this.icon,
    required this.color,
    required this.text,
    this.loading = false,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          children: [
            if (loading)
              SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(color: color, strokeWidth: 2))
            else
              Icon(icon, color: color),
            const SizedBox(width: 12),
            Text(text, style: TextStyle(color: color)),
          ],
        ),
      ),
    );
  }
}
