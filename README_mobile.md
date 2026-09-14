# CardTCGApp Mobile

A Flutter companion app for the [CardTCGApp](https://github.com/doghigh/CardTCGApp) desktop Trading Card Manager. Scan, grade, and value your trading cards on the go from any Android or iOS device.

---

## Features

- **Camera Scanning** — Capture front and back card images using your device camera or photo library
- **On-Device Condition Grading** — Automatically analyzes corner wear, edge whitening, surface defects, and centering. Runs in a background isolate so the UI stays responsive
- **Online Price Fetching** — Pulls current market prices from TCGPlayer, eBay (sold listings), and PriceCharting in parallel
- **SQLite Collection** — Same database schema as the desktop app; stores cards, valuations, and scan images locally on your device
- **Collection Browser** — Searchable list with a stats bar showing total cards, quantity, portfolio value, and net position
- **Card Detail View** — Zoomable front/back images, full metadata, defect breakdown, and price history
- **CSV Export** — Export your entire collection via the system share sheet
- **Dark Theme** — Matches the look of the desktop app

### Supported Games
Magic: The Gathering · Pokémon · Yu-Gi-Oh! · One Piece · Lorcana · Flesh and Blood · Sports · Other

---

## Requirements

- Flutter SDK **3.2.0** or later
- Dart **3.2.0** or later
- Android **5.0+ (API 21+)** or iOS **12+**
- Internet connection for price fetching

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/doghigh/CardTCGApp_Mobile.git
cd CardTCGApp_Mobile
```

### 2. Generate platform boilerplate

```bash
flutter create . --project-name card_tcg_mobile
```

> This generates the `android/` and `ios/` platform directories. Your source files won't be touched.

### 3. Install dependencies

```bash
flutter pub get
```

### 4. Run on a connected device or emulator

```bash
flutter run
```

---

## Building a Release APK (Android)

```bash
flutter build apk --release
```

The output file is at:
```
build/app/outputs/flutter-apk/app-release.apk
```

To install directly on a connected device:
```bash
flutter install
```

### Building in GitHub Codespaces

```bash
# Install Java
sudo apt-get update && sudo apt-get install -y openjdk-17-jdk

# Install Flutter
git clone https://github.com/flutter/flutter.git -b stable ~/flutter
echo 'export PATH="$PATH:$HOME/flutter/bin"' >> ~/.bashrc
source ~/.bashrc

# Accept Android SDK licenses
yes | flutter doctor --android-licenses

# Build
flutter create . --project-name card_tcg_mobile
flutter pub get
flutter build apk --release
```

---

## Project Structure

```
lib/
├── main.dart                   # App entry point, dark theme, bottom nav
├── models/
│   └── card.dart               # CardModel, Defect, ValuationModel, CollectionStats
├── db/
│   └── database.dart           # SQLite CRUD (same schema as desktop app)
├── services/
│   ├── inspector.dart          # On-device condition grading (runs in isolate)
│   └── valuator.dart           # Price fetching from TCGPlayer / eBay / PriceCharting
└── screens/
    ├── scan_screen.dart        # Camera capture, grading, metadata form, save
    ├── collection_screen.dart  # Searchable collection list, stats, CSV export
    └── detail_screen.dart      # Full card details, zoomable images, price history
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `sqflite` | Local SQLite database |
| `image_picker` | Camera and gallery access |
| `image` | On-device image analysis for condition grading |
| `http` | Price fetching from online sources |
| `path_provider` | App document directory for storing scans |
| `share_plus` | CSV export via system share sheet |
| `csv` | CSV generation |
| `intl` | Number and date formatting |

---

## Permissions

### Android
- `CAMERA` — card scanning
- `INTERNET` — price fetching
- `READ_MEDIA_IMAGES` — gallery access (Android 13+)
- `READ_EXTERNAL_STORAGE` — gallery access (Android < 13)

### iOS
- `NSCameraUsageDescription` — card scanning
- `NSPhotoLibraryUsageDescription` — gallery access

---

## Related

- **Desktop app:** [CardTCGApp](https://github.com/doghigh/CardTCGApp) — Windows desktop app with TWAIN flatbed scanner support, higher-accuracy grading, and PDF report generation
