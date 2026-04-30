import 'dart:math';
import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:image/image.dart' as img;
import '../models/card.dart';

class InspectionResult {
  final String grade;
  final double score;
  final List<Defect> defects;
  final double centeringScore;

  const InspectionResult({
    required this.grade,
    required this.score,
    required this.defects,
    required this.centeringScore,
  });

  static InspectionResult get unknown => const InspectionResult(
        grade: 'Unknown',
        score: 0,
        defects: [],
        centeringScore: 0,
      );
}

// Top-level so compute() can use it across isolates.
InspectionResult _inspectIsolate(Uint8List bytes) {
  return CardInspector()._inspectSync(bytes);
}

class CardInspector {
  static const Map<String, List<int>> _grades = {
    'Gem Mint': [95, 100],
    'Mint': [90, 94],
    'Near Mint': [80, 89],
    'Excellent': [70, 79],
    'Very Good': [60, 69],
    'Good': [50, 59],
    'Played': [35, 49],
    'Poor': [0, 34],
  };

  static const Map<String, double> _penalties = {
    'minor': 3.0,
    'moderate': 8.0,
    'severe': 18.0,
  };

  /// Runs inspection in a background isolate to keep the UI responsive.
  Future<InspectionResult> inspect(Uint8List bytes) async {
    return compute(_inspectIsolate, bytes);
  }

  InspectionResult _inspectSync(Uint8List bytes) {
    img.Image? image = img.decodeImage(bytes);
    if (image == null) return InspectionResult.unknown;

    // Resize to max 800px on the long side for reasonable speed.
    if (image.width > 800 || image.height > 800) {
      final scale = 800 / max(image.width, image.height);
      image = img.copyResize(
        image,
        width: (image.width * scale).round(),
        height: (image.height * scale).round(),
      );
    }

    final defects = <Defect>[
      ..._detectCornerDamage(image),
      ..._detectEdgeWear(image),
      ..._detectSurfaceDefects(image),
    ];
    final (centerDefects, centeringScore) = _detectCentering(image);
    defects.addAll(centerDefects);

    double score = 100.0;
    for (final d in defects) {
      score -= _penalties[d.severity] ?? 3.0;
    }
    score -= (100 - centeringScore) * 0.15;
    score = score.clamp(0.0, 100.0);

    String grade = 'Poor';
    for (final entry in _grades.entries) {
      if (score >= entry.value[0] && score <= entry.value[1]) {
        grade = entry.key;
        break;
      }
    }

    return InspectionResult(
      grade: grade,
      score: double.parse(score.toStringAsFixed(1)),
      defects: defects,
      centeringScore: double.parse(centeringScore.toStringAsFixed(1)),
    );
  }

  List<Defect> _detectCornerDamage(img.Image image) {
    final h = image.height;
    final w = image.width;
    final cs = max(10, min(h, w) ~/ 8);
    final defects = <Defect>[];

    final corners = <String, List<int>>{
      'top_left': [0, 0, cs, cs],
      'top_right': [w - cs, 0, w, cs],
      'bottom_left': [0, h - cs, cs, h],
      'bottom_right': [w - cs, h - cs, w, h],
    };

    for (final entry in corners.entries) {
      final x0 = entry.value[0];
      final y0 = entry.value[1];
      final x1 = entry.value[2];
      final y1 = entry.value[3];

      int white = 0;
      int total = 0;

      for (int y = y0; y < y1; y++) {
        for (int x = x0; x < x1; x++) {
          final p = image.getPixel(x, y);
          final lightness = (p.r + p.g + p.b) / 3.0 / 255.0;
          if (lightness > 0.90) white++;
          total++;
        }
      }

      if (total > 0) {
        final ratio = white / total;
        if (ratio > 0.35) {
          final severity =
              ratio > 0.6 ? 'severe' : ratio > 0.45 ? 'moderate' : 'minor';
          defects.add(Defect(
            type: 'corner_whitening',
            location: entry.key,
            severity: severity,
            metric: ratio,
          ));
        }
      }
    }
    return defects;
  }

  List<Defect> _detectEdgeWear(img.Image image) {
    final h = image.height;
    final w = image.width;
    final et = max(3, min(h, w) ~/ 60);
    final defects = <Defect>[];

    final regions = [
      ('top', 0, 0, w, et),
      ('bottom', 0, h - et, w, h),
      ('left', 0, 0, et, h),
      ('right', w - et, 0, w, h),
    ];

    for (final (name, x0, y0, x1, y1) in regions) {
      int white = 0;
      int total = 0;

      for (int y = y0; y < y1; y++) {
        for (int x = x0; x < x1; x++) {
          final p = image.getPixel(x, y);
          final lightness = (p.r + p.g + p.b) / 3.0 / 255.0;
          if (lightness > 0.90) white++;
          total++;
        }
      }

      if (total > 0) {
        final ratio = white / total;
        if (ratio > 0.30) {
          final severity =
              ratio > 0.55 ? 'severe' : ratio > 0.40 ? 'moderate' : 'minor';
          defects.add(Defect(
            type: 'edge_whitening',
            location: name,
            severity: severity,
            metric: ratio,
          ));
        }
      }
    }
    return defects;
  }

  List<Defect> _detectSurfaceDefects(img.Image image) {
    final defects = <Defect>[];
    final h = image.height;
    final w = image.width;
    final crop = max(10, min(h, w) ~/ 20);

    if (h - 2 * crop <= 0 || w - 2 * crop <= 0) return defects;

    double sum = 0;
    double sumSq = 0;
    int count = 0;
    int darkCount = 0;

    for (int y = crop; y < h - crop; y++) {
      for (int x = crop; x < w - crop; x++) {
        final p = image.getPixel(x, y);
        final brightness = (p.r + p.g + p.b) / 3.0;
        sum += brightness;
        sumSq += brightness * brightness;
        count++;
        // Dark anomaly check (staining)
        if (brightness < 60 &&
            (p.r + p.g + p.b) / 3.0 < 60 &&
            _saturation(p.r.toDouble(), p.g.toDouble(), p.b.toDouble()) < 0.2) {
          darkCount++;
        }
      }
    }

    if (count > 0) {
      final mean = sum / count;
      final variance = (sumSq / count) - (mean * mean);
      if (variance < 100) {
        defects.add(Defect(
          type: 'low_sharpness',
          location: 'overall',
          severity: 'minor',
          metric: variance,
        ));
      }

      final darkRatio = darkCount / count;
      if (darkRatio > 0.08) {
        defects.add(Defect(
          type: 'surface_staining',
          location: 'center',
          severity: darkRatio > 0.15 ? 'moderate' : 'minor',
          metric: darkRatio,
        ));
      }
    }

    return defects;
  }

  (List<Defect>, double) _detectCentering(img.Image image) {
    final h = image.height;
    final w = image.width;

    int top = h, bottom = 0, left = w, right = 0;

    for (int y = 0; y < h; y++) {
      for (int x = 0; x < w; x++) {
        final p = image.getPixel(x, y);
        final lightness = (p.r + p.g + p.b) / 3.0 / 255.0;
        if (lightness < 0.85) {
          if (y < top) top = y;
          if (y > bottom) bottom = y;
          if (x < left) left = x;
          if (x > right) right = x;
        }
      }
    }

    if (top >= bottom || left >= right) return ([], 100.0);

    final lb = left;
    final rb = w - right;
    final tb = top;
    final bb = h - bottom;

    double edgeRatio(int a, int b) {
      final mx = max(a, b);
      return mx > 0 ? min(a, b) / mx : 1.0;
    }

    final hc = edgeRatio(lb, rb);
    final vc = edgeRatio(tb, bb);
    final score = (hc + vc) / 2 * 100;

    final defects = <Defect>[];
    if (score < 70) {
      final severity =
          score < 50 ? 'severe' : score < 60 ? 'moderate' : 'minor';
      defects.add(Defect(
        type: 'off_centering',
        location: 'h:${hc.toStringAsFixed(2)}/v:${vc.toStringAsFixed(2)}',
        severity: severity,
        metric: score,
      ));
    }
    return (defects, score);
  }

  double _saturation(double r, double g, double b) {
    final max = [r, g, b].reduce((a, b) => a > b ? a : b);
    final min = [r, g, b].reduce((a, b) => a < b ? a : b);
    if (max == 0) return 0;
    return (max - min) / max;
  }
}
