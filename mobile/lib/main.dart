import 'package:flutter/material.dart';
import 'screens/scan_screen.dart';
import 'screens/collection_screen.dart';

void main() {
  runApp(const CardTCGApp());
}

class CardTCGApp extends StatelessWidget {
  const CardTCGApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Card TCG Manager',
      debugShowCheckedModeBanner: false,
      theme: _buildTheme(),
      home: const _HomeShell(),
    );
  }

  ThemeData _buildTheme() {
    const bg = Color(0xFF1a202c);
    const surface = Color(0xFF2d3748);
    const primary = Color(0xFF4299e1);
    const onPrimary = Colors.white;
    const textColor = Color(0xFFe2e8f0);

    return ThemeData(
      brightness: Brightness.dark,
      colorScheme: ColorScheme.dark(
        primary: primary,
        onPrimary: onPrimary,
        secondary: const Color(0xFF38a169),
        surface: surface,
        onSurface: textColor,
        error: const Color(0xFFe53e3e),
      ),
      scaffoldBackgroundColor: bg,
      cardColor: surface,
      appBarTheme: const AppBarTheme(
        backgroundColor: Color(0xFF2c3e50),
        foregroundColor: textColor,
        elevation: 0,
        centerTitle: false,
      ),
      cardTheme: CardTheme(
        color: surface,
        elevation: 2,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: bg,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(6),
          borderSide: const BorderSide(color: Color(0xFF4a5568)),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(6),
          borderSide: const BorderSide(color: Color(0xFF4a5568)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(6),
          borderSide: const BorderSide(color: primary, width: 1.5),
        ),
        labelStyle: const TextStyle(color: Color(0xFF718096)),
        hintStyle: const TextStyle(color: Color(0xFF718096)),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primary,
          foregroundColor: onPrimary,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: primary,
          side: const BorderSide(color: Color(0xFF4a5568)),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
        ),
      ),
      switchTheme: SwitchThemeData(
        thumbColor: WidgetStateProperty.resolveWith(
            (s) => s.contains(WidgetState.selected) ? primary : null),
        trackColor: WidgetStateProperty.resolveWith(
            (s) => s.contains(WidgetState.selected)
                ? primary.withOpacity(0.4)
                : null),
      ),
      dividerTheme: const DividerThemeData(color: Color(0xFF4a5568), thickness: 0.5),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: Color(0xFF2d3748),
        selectedItemColor: primary,
        unselectedItemColor: Color(0xFF718096),
      ),
      useMaterial3: true,
    );
  }
}

class _HomeShell extends StatefulWidget {
  const _HomeShell();

  @override
  State<_HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<_HomeShell> {
  int _index = 0;

  // Keep screens alive when switching tabs.
  final _scanKey = GlobalKey<State>();
  final _collKey = GlobalKey<State>();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _index,
        children: [
          ScanScreen(key: _scanKey),
          CollectionScreen(key: _collKey),
        ],
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _index,
        onTap: (i) => setState(() => _index = i),
        items: const [
          BottomNavigationBarItem(
            icon: Icon(Icons.document_scanner_outlined),
            activeIcon: Icon(Icons.document_scanner),
            label: 'Scan',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.style_outlined),
            activeIcon: Icon(Icons.style),
            label: 'Collection',
          ),
        ],
      ),
    );
  }
}
