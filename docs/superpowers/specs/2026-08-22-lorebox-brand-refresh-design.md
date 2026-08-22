# LoreBox Brand Refresh — Design

## Context

`assets/generate_assets.py` ships with placeholder branding (its own docstring
says so): a generic indigo card-stack glyph on `#5865f2`, plain "Segoe UI"
typography, and "Lorebox" casing throughout.

A real brand kit now exists at the repo root (`brand.pdf` /
`LoreBox Brand Kit.html`): a heraldic "LB" monogram crest with a three-card
fan, on a Royal Blue / Crimson / Gold / Parchment / Ink palette, set in
Cinzel (headers/wordmark) and Manrope (UI/body). No production art files
exist yet — only this overview mockup — so the crest itself will be built as
flat/vector art in code rather than sourced from a painterly original.

## Goals

- Replace the placeholder accent color, icon/logo assets, and body typeface
  with the LoreBox brand kit's palette, crest, and fonts.
- Update user-visible "Lorebox" text to "LoreBox" across the app, docs, and
  Store listing.
- Keep the change mechanical and low-risk: same file paths/names for
  regenerated assets, same internal identifiers, same package identity.

## Non-goals

- No painterly/gradient-heavy icon art — brand kit's own usage notes require
  the icon to resolve to a clean silhouette at 32px, which flat vector art
  serves better anyway.
- No renaming of Python modules, packages, the `.spec` file, folder names, or
  the MSIX package `Identity/Name` (`33303JesseCatlow.Lorebox` is registered
  with Partner Center and must not change).
- No changes to functional/semantic colors (`SUCCESS` green) — only the
  identity palette (`ACCENT`, `WARNING`, `DANGER`) and neutrals.

## Design

### 1. Theme tokens (`utils/theme.py`)

- `DEFAULT_ACCENT` → Royal Blue `#1A3A6B` (was `#5865f2`).
- New named tokens: `CRIMSON = "#A51C2C"`, `GOLD = "#D1A437"`,
  `PARCHMENT = "#E7E1C9"`.
- `WARNING` → Gold, `DANGER` → Crimson (both already semantically close to
  their current amber/red values).
- `SUCCESS` (`#43b581`) stays unchanged — it's a functional status color,
  not part of the brand identity palette.
- `BG_DEEP`/`BG_BASE`/`BG_RAISED`/`BG_HOVER`/`BORDER` stay dark-mode but
  re-derived from Ink `#0E0E12` (close to today's `#0d0f18` — minimal visual
  change).
- `TEXT_PRI` stays a light neutral, not literally Parchment — Parchment on
  dark backgrounds reads poorly across dense data tables (collection grid,
  reports). Parchment is reserved for accent/heading use, per section 2.
- High-contrast mode (`_tokens(high_contrast=True)`) is unaffected — it
  already overrides to pure black/white and isn't part of brand identity.

### 2. Typography

- Bundle `Cinzel` and `Manrope` (`.ttf`, both SIL Open Font License — free to
  embed) under `assets/fonts/`.
- Load both via `QFontDatabase.addApplicationFont()` in `main.py` at
  startup, before `apply_dark_theme()` runs.
- `build_stylesheet()`'s global `*` rule switches `font-family` from
  `"Segoe UI"` to `"Manrope", "Segoe UI", sans-serif`.
- Add a `heading="true"` dynamic Qt property (same pattern as the existing
  `primary="true"` on `QPushButton`) for section-header `QLabel`s (tab
  headers like "📊 Dashboard", dialog titles). Styled with
  `font-family: "Cinzel", Georgia, serif`, Gold or Parchment color,
  slightly increased letter-spacing.
- The OS-drawn window title bar text (`setWindowTitle`) cannot take a custom
  font — it stays plain system font, text updated per section 5.

### 3. Icon & asset regeneration (`assets/generate_assets.py`)

Rewrite the icon renderer (keeping the existing multi-size pipeline and all
output filenames/paths unchanged):

- Badge shape: rounded-square (Store tile shape) and circular (favicon/
  avatar) variants, Ink `#0E0E12` background, thin Gold ring border.
- Monogram: bold serif "LB" (Cinzel Bold, loaded via `PIL.ImageFont` from
  the bundled TTF) rendered in Gold, with a cheap dual-tone heraldic effect —
  a Crimson-tinted copy offset slightly right and a Royal-Blue-tinted copy
  offset slightly left, underneath the primary Gold glyph.
- Three-card fan motif at the base of the badge, per the brand kit's fixed
  identity rule: blue-faced card left, gold-faced card center (small
  parchment/crimson diamond "gem" accent), crimson-faced card right.
- At favicon/taskbar sizes (≤44px, matching today's `monogram=True` path in
  `render()`), drop the card fan — monogram-only in solid Gold, per the
  brand kit's own note that the mark should "resolve to a single gold
  silhouette" at small sizes.
- Maintain ≥12% clear space padding around the crest, per usage notes.
- Wordmark lockups (`wordmark.png`, `wordmark_on_accent.png`): "LoreBox" set
  in Cinzel, icon glyph to the left — same lockup structure as today,
  re-themed.
- Regenerate and commit the actual output files (icon.ico, all `Square*`/
  `Wide*`/`Store*` PNGs, `store/AppTileIcon_*`, `store/BoxArt_1080x1080.png`,
  `store/PosterArt_720x1080.png`) so the build doesn't require re-running
  Pillow generation — matching how assets are checked in today.

### 4. Accent presets (`utils/themes.py`)

- `"Default — Indigo": "#5865f2"` → `"Default — Royal Blue": "#1A3A6B"`.
- All sports-team and TCG mana-color presets are untouched — those are
  user-selectable accents for personalizing to their own collection/team,
  independent of LoreBox's own brand identity.

### 5. Copy & naming (display text only)

"Lorebox" → "LoreBox" in user-visible strings only:

- `ui/main_window.py`: `setWindowTitle("Lorebox v1.3.0")` and the welcome
  dialog title.
- `README.md`, `README-Linux.md`, `README-macOS.md`, `ONBOARDING.md`,
  `STORE_LISTING.md`, `PRIVACY.md`, `BUILD.md`.
- In-app dialog/help strings in `ui/help_content.py`, `ui/help_dialog.py`,
  and any other user-facing labels that spell out the product name.
- `LICENSE` copyright line, if it currently reads "Lorebox".

Left unchanged (identifiers, not display text): Python module/package
names, file paths, `Lorebox.spec`, folder names, `.env`/`.env.example`
variable names, git remote, class/variable names, and the MSIX package
`Identity/Name` (`33303JesseCatlow.Lorebox`).

### 6. Packaging (`packaging/AppxManifest.xml`)

- `<DisplayName>Lorebox</DisplayName>` → `LoreBox` (both the package-level
  and `Application` element's `DisplayName` attribute).
- `<Description>` text refreshed to match the updated copy voice, keeping
  the same factual content ("Catalog, grade, and value your trading card
  collection.").
- `Identity Name`, `Package Family Name`, and `Executable` stay exactly as
  registered with Partner Center — changing these would break the existing
  Store listing association.
- `packaging/staging/AppxManifest.xml` is a gitignored build artifact
  (regenerated by `build_msix.ps1`) — not hand-edited.

## Testing

- `tests/test_theme.py`: update any hardcoded color assertions to the new
  token values; confirm `build_stylesheet()` and `apply_dark_theme()` still
  run cleanly with the new `DEFAULT_ACCENT` and font-family.
- Manual verification: launch the app, confirm the new accent renders
  correctly in both normal and high-contrast mode, confirm bundled fonts
  load (no fallback-to-Segoe-UI warnings), and visually check the
  regenerated icon at 16px/32px/256px for legibility.
- Manual verification of `assets/generate_assets.py` output: run it and
  inspect the generated icon set before committing the regenerated files.
