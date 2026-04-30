import 'dart:convert';

class Defect {
  final String type;
  final String location;
  final String severity;
  final double metric;

  const Defect({
    required this.type,
    required this.location,
    required this.severity,
    required this.metric,
  });

  Map<String, dynamic> toJson() => {
        'type': type,
        'location': location,
        'severity': severity,
        'metric': metric,
      };

  factory Defect.fromJson(Map<String, dynamic> json) => Defect(
        type: json['type'] as String,
        location: json['location'] as String,
        severity: json['severity'] as String,
        metric: (json['metric'] as num).toDouble(),
      );

  String get displayType => type
      .split('_')
      .map((w) => w.isEmpty ? '' : w[0].toUpperCase() + w.substring(1))
      .join(' ');
}

class CardModel {
  final int? id;
  final String name;
  final String? setName;
  final String? cardNumber;
  final String? rarity;
  final String? game;
  final int? year;
  final String language;
  final bool foil;
  final String? frontScanPath;
  final String? backScanPath;
  final String? conditionGrade;
  final double? conditionScore;
  final List<Defect> defects;
  final double estimatedValue;
  final double purchasePrice;
  final String? purchaseDate;
  final String? notes;
  final int quantity;
  final String? createdAt;
  final String? updatedAt;

  const CardModel({
    this.id,
    required this.name,
    this.setName,
    this.cardNumber,
    this.rarity,
    this.game,
    this.year,
    this.language = 'English',
    this.foil = false,
    this.frontScanPath,
    this.backScanPath,
    this.conditionGrade,
    this.conditionScore,
    this.defects = const [],
    this.estimatedValue = 0.0,
    this.purchasePrice = 0.0,
    this.purchaseDate,
    this.notes,
    this.quantity = 1,
    this.createdAt,
    this.updatedAt,
  });

  Map<String, dynamic> toMap() => {
        if (id != null) 'id': id,
        'name': name,
        'set_name': setName,
        'card_number': cardNumber,
        'rarity': rarity,
        'game': game,
        'year': year,
        'language': language,
        'foil': foil ? 1 : 0,
        'front_scan_path': frontScanPath,
        'back_scan_path': backScanPath,
        'condition_grade': conditionGrade,
        'condition_score': conditionScore,
        'defects_json': jsonEncode(defects.map((d) => d.toJson()).toList()),
        'estimated_value': estimatedValue,
        'purchase_price': purchasePrice,
        'purchase_date': purchaseDate,
        'notes': notes,
        'quantity': quantity,
      };

  factory CardModel.fromMap(Map<String, dynamic> map) {
    List<Defect> defects = [];
    try {
      final raw = jsonDecode(map['defects_json'] as String? ?? '[]') as List;
      defects = raw.map((e) => Defect.fromJson(e as Map<String, dynamic>)).toList();
    } catch (_) {}

    return CardModel(
      id: map['id'] as int?,
      name: map['name'] as String? ?? 'Unknown',
      setName: map['set_name'] as String?,
      cardNumber: map['card_number'] as String?,
      rarity: map['rarity'] as String?,
      game: map['game'] as String?,
      year: map['year'] as int?,
      language: map['language'] as String? ?? 'English',
      foil: (map['foil'] as int? ?? 0) != 0,
      frontScanPath: map['front_scan_path'] as String?,
      backScanPath: map['back_scan_path'] as String?,
      conditionGrade: map['condition_grade'] as String?,
      conditionScore: (map['condition_score'] as num?)?.toDouble(),
      defects: defects,
      estimatedValue: (map['estimated_value'] as num? ?? 0).toDouble(),
      purchasePrice: (map['purchase_price'] as num? ?? 0).toDouble(),
      purchaseDate: map['purchase_date'] as String?,
      notes: map['notes'] as String?,
      quantity: map['quantity'] as int? ?? 1,
      createdAt: map['created_at'] as String?,
      updatedAt: map['updated_at'] as String?,
    );
  }

  CardModel copyWith({
    int? id,
    String? name,
    String? setName,
    String? cardNumber,
    String? rarity,
    String? game,
    int? year,
    String? language,
    bool? foil,
    String? frontScanPath,
    String? backScanPath,
    String? conditionGrade,
    double? conditionScore,
    List<Defect>? defects,
    double? estimatedValue,
    double? purchasePrice,
    String? purchaseDate,
    String? notes,
    int? quantity,
  }) =>
      CardModel(
        id: id ?? this.id,
        name: name ?? this.name,
        setName: setName ?? this.setName,
        cardNumber: cardNumber ?? this.cardNumber,
        rarity: rarity ?? this.rarity,
        game: game ?? this.game,
        year: year ?? this.year,
        language: language ?? this.language,
        foil: foil ?? this.foil,
        frontScanPath: frontScanPath ?? this.frontScanPath,
        backScanPath: backScanPath ?? this.backScanPath,
        conditionGrade: conditionGrade ?? this.conditionGrade,
        conditionScore: conditionScore ?? this.conditionScore,
        defects: defects ?? this.defects,
        estimatedValue: estimatedValue ?? this.estimatedValue,
        purchasePrice: purchasePrice ?? this.purchasePrice,
        purchaseDate: purchaseDate ?? this.purchaseDate,
        notes: notes ?? this.notes,
        quantity: quantity ?? this.quantity,
        createdAt: createdAt,
        updatedAt: updatedAt,
      );
}

class ValuationModel {
  final int? id;
  final int cardId;
  final String source;
  final double value;
  final String currency;
  final String? url;
  final String? fetchedAt;

  const ValuationModel({
    this.id,
    required this.cardId,
    required this.source,
    required this.value,
    this.currency = 'USD',
    this.url,
    this.fetchedAt,
  });

  Map<String, dynamic> toMap() => {
        if (id != null) 'id': id,
        'card_id': cardId,
        'source': source,
        'value': value,
        'currency': currency,
        'url': url,
      };

  factory ValuationModel.fromMap(Map<String, dynamic> map) => ValuationModel(
        id: map['id'] as int?,
        cardId: map['card_id'] as int,
        source: map['source'] as String,
        value: (map['value'] as num).toDouble(),
        currency: map['currency'] as String? ?? 'USD',
        url: map['url'] as String?,
        fetchedAt: map['fetched_at'] as String?,
      );
}

class CollectionStats {
  final int totalCards;
  final int totalQuantity;
  final double totalValue;
  final double totalCost;
  final double avgCondition;

  const CollectionStats({
    this.totalCards = 0,
    this.totalQuantity = 0,
    this.totalValue = 0,
    this.totalCost = 0,
    this.avgCondition = 0,
  });

  double get netPosition => totalValue - totalCost;

  factory CollectionStats.fromMap(Map<String, dynamic> map) => CollectionStats(
        totalCards: (map['total_cards'] as int?) ?? 0,
        totalQuantity: (map['total_quantity'] as int?) ?? 0,
        totalValue: (map['total_value'] as num? ?? 0).toDouble(),
        totalCost: (map['total_cost'] as num? ?? 0).toDouble(),
        avgCondition: (map['avg_condition'] as num? ?? 0).toDouble(),
      );
}
