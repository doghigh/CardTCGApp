import 'dart:async';
import 'package:http/http.dart' as http;

class ValuationResult {
  final String source;
  final double value;
  final String? url;

  const ValuationResult({
    required this.source,
    required this.value,
    this.url,
  });
}

class CardValuator {
  static const _headers = {
    'User-Agent':
        'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
  };
  static const _timeout = Duration(seconds: 12);

  Future<List<ValuationResult>> fetchAll(String name, {String? setName}) async {
    final query = setName != null && setName.isNotEmpty ? '$name $setName' : name;
    final results = await Future.wait(
      [
        _fetchTcgPlayer(query),
        _fetchEbaySold(query),
        _fetchPriceCharting(query),
      ],
      eagerError: false,
    );
    return results.whereType<ValuationResult>().toList();
  }

  double computeEstimate(List<ValuationResult> results, double conditionScore) {
    if (results.isEmpty) return 0.0;
    final prices = results.map((r) => r.value).toList()..sort();
    final median = prices[prices.length ~/ 2];
    final multiplier = (conditionScore / 85.0).clamp(0.2, 1.2);
    return double.parse((median * multiplier).toStringAsFixed(2));
  }

  Future<ValuationResult?> _fetchTcgPlayer(String query) async {
    try {
      final encoded = Uri.encodeComponent(query);
      final url = 'https://www.tcgplayer.com/search/all/product?q=$encoded';
      final resp = await http
          .get(Uri.parse(url), headers: _headers)
          .timeout(_timeout);
      if (resp.statusCode != 200) return null;

      final price = _extractFirstPrice(resp.body);
      if (price == null) return null;
      return ValuationResult(source: 'TCGPlayer', value: price, url: url);
    } catch (_) {
      return null;
    }
  }

  Future<ValuationResult?> _fetchEbaySold(String query) async {
    try {
      final encoded = Uri.encodeComponent('$query card');
      final url =
          'https://www.ebay.com/sch/i.html?_nkw=$encoded&LH_Sold=1&LH_Complete=1';
      final resp = await http
          .get(Uri.parse(url), headers: _headers)
          .timeout(_timeout);
      if (resp.statusCode != 200) return null;

      final prices = _extractAllPrices(resp.body, selector: 's-item__price');
      if (prices.isEmpty) return null;
      prices.sort();
      final trimmed = prices.length > 4
          ? prices.sublist(prices.length ~/ 4, prices.length * 3 ~/ 4)
          : prices;
      final avg = trimmed.reduce((a, b) => a + b) / trimmed.length;
      return ValuationResult(
          source: 'eBay (sold)',
          value: double.parse(avg.toStringAsFixed(2)),
          url: url);
    } catch (_) {
      return null;
    }
  }

  Future<ValuationResult?> _fetchPriceCharting(String query) async {
    try {
      final encoded = Uri.encodeComponent(query);
      final url =
          'https://www.pricecharting.com/search-products?q=$encoded&type=prices';
      final resp = await http
          .get(Uri.parse(url), headers: _headers)
          .timeout(_timeout);
      if (resp.statusCode != 200) return null;

      final price = _extractFirstPrice(resp.body);
      if (price == null) return null;
      return ValuationResult(source: 'PriceCharting', value: price, url: url);
    } catch (_) {
      return null;
    }
  }

  double? _extractFirstPrice(String html) {
    final match = RegExp(r'\$([\d,]+\.\d{2})').firstMatch(html);
    if (match == null) return null;
    return double.tryParse(match.group(1)!.replaceAll(',', ''));
  }

  List<double> _extractAllPrices(String html, {required String selector}) {
    final prices = <double>[];
    // Find spans/divs containing the selector class, then parse prices from them.
    final classPattern = RegExp(
        'class="[^"]*$selector[^"]*"[^>]*>([^<]{0,200})<',
        dotAll: true);
    for (final m in classPattern.allMatches(html)) {
      for (final pm in RegExp(r'\$([\d,]+\.\d{2})').allMatches(m.group(1)!)) {
        final v = double.tryParse(pm.group(1)!.replaceAll(',', ''));
        if (v != null && v > 0) prices.add(v);
      }
    }
    // Fallback: scan all dollar amounts in the page.
    if (prices.isEmpty) {
      for (final pm in RegExp(r'\$([\d,]+\.\d{2})').allMatches(html)) {
        final v = double.tryParse(pm.group(1)!.replaceAll(',', ''));
        if (v != null && v > 0 && v < 50000) prices.add(v);
      }
    }
    return prices;
  }
}
