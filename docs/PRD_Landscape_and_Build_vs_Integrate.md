# Lorebox — Landscape & Build-vs-Integrate PRD

**Status:** Draft for review
**Author:** Generated for Jesse Catlow
**Date:** 2026-06-18
**Purpose:** Inventory the open-source projects, CLIs, public APIs, MCP servers, and Python
libraries that already implement the capabilities Lorebox provides, so we can decide—per
capability—whether to **keep building**, **adopt a library**, **integrate an API**, or
**learn from a competitor**. This is a research/due-diligence PRD, not a feature spec.

---

## 1. What Lorebox does today (capability inventory)

Confirmed by reading the codebase (`core/`, `ui/`, `ebay_webhook/`, packaging):

| # | Capability | Current implementation in Lorebox |
|---|------------|-----------------------------------|
| A | **Image acquisition / scanning** | `core/scanner.py` — `twain` lib, flatbed + ADF duplex, DPI/bit-depth control, OpenCV denoise + unsharp enhancement |
| B | **Card identification** | `core/identifier.py` — Claude vision (`claude-haiku-4-5`) primary, Tesseract OCR fallback; extracts name/set/number/rarity/year/game across MTG, Pokémon, Yu-Gi-Oh!, One Piece, Lorcana, sports, non-sport |
| C | **Catalog / card data** | None held locally — relies on the identifier's free-text output; no canonical card DB |
| D | **Pricing / valuation** | `core/valuator.py` — Scryfall (MTG, official), eBay Browse API (everything else, OAuth client-credentials), condition multipliers; PriceCharting scrape retired; TradingCardAPI planned |
| E | **Condition grading** | `core/inspector.py` — pure OpenCV heuristics: corners, edges, surface creases/staining, centering → 8-tier grade + 0–100 score |
| F | **Collection storage** | `core/database.py` — local SQLite (cards, valuations, reports, value_history), dedup/merge, quantity, stats, per-game/grade/set breakdowns, value snapshots |
| G | **Batch & automation** | `core/watcher.py` folder watch, CSV/folder batch import w/ column mapping, continuous scan mode |
| H | **Reports / analytics** | `core/reports_generator.py` — reportlab monthly PDF; `ui/dashboard_tab.py` charts |
| I | **AI-agent surface** | `cardchain` MCP server (search_cards, get_card_price, get_population, should_i_grade, portfolio, listings, player_stats) |
| J | **Auth / packaging** | `core/auth.py` (pyotp TOTP + Windows Hello), PyInstaller single-exe, MSIX, eBay account-deletion webhook on Render |

**Design constraints to preserve:** privacy-first / local-only, Windows desktop, official-APIs-only
(no ToS-risky scraping), no mandatory login.

---

## 2. Landscape by capability

For each area: closest existing work → gap vs. Lorebox → recommendation.

### A. Image acquisition / scanning

| Option | Type | Notes |
|--------|------|-------|
| [pytwain](https://pytwain.readthedocs.io/) | Python lib | ctypes TWAIN wrapper, no compile; what Lorebox effectively uses |
| [twain-wia-sane-scanner](https://pypi.org/project/twain-wia-sane-scanner) | Python lib | TWAIN **+ WIA + SANE + ICA + eSCL** — broader device coverage than TWAIN-only |
| [wia_scan](https://pypi.org/project/wia_scan/) | Python lib | Pure WIA; works with "Windows Fax and Scan"-class devices |

**Gap:** Lorebox is TWAIN-only; many consumer scanners ship WIA but flaky TWAIN.
**Recommendation:** **Adopt a library.** Add a WIA fallback (`wia_scan` or the unified
`twain-wia-sane-scanner`) so non-TWAIN scanners and webcams aren't dead ends. Low effort, removes a real support cliff.

### B. Card identification (recognition / OCR / vision)

| Option | Type | Notes |
|--------|------|-------|
| [tcg-ocr-scanner](https://github.com/starstuffharvestingstarlight/tcg-ocr-scanner) | OSS | Tesseract + OpenCV TCG scanner — same fallback stack Lorebox has |
| [Yet-Another-Magic-Card-Recognizer](https://github.com/ForOhForError/Yet-Another-Magic-Card-Recognizer) | OSS | Perceptual-hash MTG recognizer |
| [hj3yoo/mtg_card_detector](https://github.com/hj3yoo/mtg_card_detector) | OSS | CV detection + pHash match against Scryfall image hashes |
| [PokeCard-TCG-detector](https://github.com/em4go/PokeCard-TCG-detector) | OSS | OpenCV + `imagehash` vs Pokémon API images |
| [Moss Machine](https://kairicollections.github.io/Moss-Machines-Magic-the-Gathering-sorting/) | OSS project | Sorting/recognition framework claiming 317 games |
| Ximilar [card identification API](https://www.ximilar.com/blog/how-to-scan-and-identify-your-trading-cards-with-ximilar-ai/) | Commercial API | AI identify + slab/cert detection |

**Key technique we're not using:** **perceptual hashing against Scryfall/Pokémon bulk
images.** Download bulk images once, precompute pHash/dHash, match offline. This is
**deterministic, free, fully local, and exact** (returns the precise printing/set), whereas
Claude-vision returns free-text that can hallucinate set/number and costs per call.

**Gap:** Lorebox's vision path has no ground-truth catalog to validate against (see C), so the
output can be confidently wrong. The OCR fallback is acknowledged "degraded."
**Recommendation:** **Build (using proven OSS technique) + keep vision as a tie-breaker.**
Add an offline pHash matcher for MTG/Pokémon (highest-volume games) to make IDs exact and
free; fall back to Claude-vision only when the hash is ambiguous or the game lacks bulk image
data. This directly improves accuracy *and* cuts API spend.

### C. Catalog / card data (the missing backbone)

| Option | Type | Notes |
|--------|------|-------|
| [Scryfall bulk data](https://scryfall.com/docs/api) + [Scrython](https://github.com/NandaScott/Scrython) | API/SDK | Full MTG catalog + images, free, redistributable; Scrython 2.0 has built-in rate limiting |
| [Pokémon TCG API](https://github.com/PokemonTCG/pokemon-tcg-api) / `pokemontcgsdk` | API/SDK | Canonical Pokémon catalog |
| [TCGdex](https://tcgdex.dev/) | API | Free Pokémon catalog + market hooks, **no key** |
| [YGOPRODeck](https://ygoprodeck.com/api-guide/) | API | Free Yu-Gi-Oh! catalog + prices |
| [open-cards](https://codeberg.org/open-cards/open-cards) | OSS dataset | Open multi-game card DB for collectors |

**Gap:** This is the **single biggest architectural hole.** Lorebox treats identification
output as truth instead of resolving it against a canonical catalog. A local catalog would:
fix IDs, enable exact pricing keys, power set-completion tracking, and feed the pHash matcher in B.
**Recommendation:** **Integrate (ingest bulk → local cache).** Ship a periodically-refreshed
local catalog (Scryfall bulk for MTG; Pokémon TCG/TCGdex; YGOPRODeck) in SQLite alongside the
collection. Stays privacy-first (data is local), and becomes the foundation that B/D/H build on.

### D. Pricing / valuation

| Option | Type | Notes | Games |
|--------|------|-------|-------|
| Scryfall | API (in use) | Free, official USD | MTG |
| eBay Browse | API (in use) | Active listings only — **not sold comps** | All |
| [JustTCG](https://justtcg.com/) | API | Condition-specific + foil + bulk lookups | MTG/PKM/YGO/+ |
| [TCGdex markets](https://tcgdex.dev/markets-prices) | API | Cardmarket + TCGplayer, no key | Pokémon |
| [TCG API (tcgapi.dev)](https://tcgapi.dev/) | API | 85+ games, daily refresh, 100 req/day free | Many |
| [TCG Price Lookup](https://tcgpricelookup.com/) | API | TCGplayer + eBay + **PSA/BGS/CGC graded** prices, 300k cards | 8 games |
| eBay [Marketplace Insights](https://community.ebay.com/t5/eBay-APIs-Talk-to-your-fellow/Marketplace-Insights-API/td-p/34699452) | API | **Sold comps — gated to approved partners; effectively closed to indies in 2026** |

**Gap:** Lorebox prices non-MTG cards off eBay **active** listings × 0.85 — a proxy for sold
value, not real comps. True sold data via eBay is now partner-gated.
**Recommendation:** **Integrate a multi-game pricing API** (JustTCG or tcgapi.dev) as the
primary non-MTG source, with condition/foil-aware keys (pairs perfectly with the grade we
already compute). Keep eBay Browse as a secondary/sanity source. This is the most direct
accuracy win after the catalog. Note the planned "TradingCardAPI" TODO can be satisfied here.

### E. Condition grading

| Option | Type | Notes |
|--------|------|-------|
| [crimsonthinker/psa_pokemon_cards](https://github.com/crimsonthinker/psa_pokemon_cards) | OSS | Transfer-learning (VGG/ResNet/MobileNet) on PSA 4-subscore model |
| [rthorst/mint_condition](https://github.com/rthorst/mint_condition) | OSS | ResNet-18 trained on ~90k eBay-graded cards |
| [pokemon-card-analyzer](https://github.com/NickPiscitelli/pokemon-card-analyzer) | OSS | **Fully in-browser/local** centering grade — aligns with privacy stance |
| [Ximilar Card Grading](https://docs.ximilar.com/services/card_grading/) | Commercial API | Per-corner/edge/surface/centering, slab/cert recognition, "pre-grading" framing |

**Gap:** Lorebox grading is hand-tuned OpenCV heuristics — explainable and local (good), but
brittle vs. learned models, and there's no slab/cert detection for already-graded cards.
**Recommendation:** **Keep building, selectively borrow.** The local heuristic approach is a
genuine differentiator (no upload, explainable defects). Borrow the **4-subscore output
structure** (centering/corners/edges/surface as separate scores) from the PSA-style OSS models
to make grades more legible, and add **slab/cert detection** (an OCR pattern, or Ximilar) so
already-slabbed cards are recognized rather than re-graded. Don't outsource the core grader.

### F. Collection management (full-app comparables to learn from)

| Project | Type | Why it's relevant |
|---------|------|-------------------|
| [Spellbook](https://github.com/KyleDerZweite/spellbook) | OSS, self-host | Mobile scan + OCR + sync; closest architectural cousin (MTG only) |
| [pokecollector](https://github.com/Git-Romer/pokecollector) | OSS, self-host | TCGdex data, Cardmarket/TCGplayer prices, binders, **portfolio analytics**, optional AI recognition, backups |
| [OpenMTG](https://github.com/DredBaron/OpenMTG) | OSS | FastAPI+React inventory, deck building, stats, import/export |
| [Card-Collection-Manager-2](https://github.com/sebastiandine/Card-Collection-Manager-2) | OSS | Tauri (Rust/TS) **native desktop multi-game** — direct desktop comparable |

**Gap:** These mostly assume catalog-driven entry (pick from a DB); Lorebox's
**scanner-first + CV-grading** flow is differentiated. But they're ahead on portfolio
analytics, binders/wishlists, and deck/export interop.
**Recommendation:** **Learn, don't adopt.** Lorebox's local desktop + scanner + grading niche
is defensible. Mine these for roadmap features (binders, wishlists, set-completion, richer
portfolio analytics, deck/CSV interop) rather than replatforming.

### G / H. Reports, MCP, auth, packaging

- **Reports:** reportlab is the right call; no compelling OSS to swap in. Keep.
- **MCP:** Your `cardchain` MCP is ahead of the public field — comparable servers exist but
  are read-only catalog/price lookups:
  [scryfall-local](https://github.com/findingsimple/scryfall-local) (local SQLite+FTS5 cache —
  a good model for the §C catalog),
  [ptcg-mcp](https://github.com/jlgrimes/ptcg-mcp),
  [pokemon-tcg-mcp](https://github.com/grzetich/pokemon-tcg-mcp),
  [mtg-mcp-servers](https://github.com/artillect/mtg-mcp-servers).
  **Recommendation:** keep building cardchain; consider `scryfall-local`'s FTS5 pattern for the
  local catalog.
- **Auth/packaging:** pyotp + Windows Hello + PyInstaller/MSIX are standard and fine. No change.

---

## 3. Prioritized recommendations

| Priority | Action | Type | Why now |
|----------|--------|------|---------|
| **P0** | Ship a **local canonical catalog** (Scryfall bulk + Pokémon + YGO) in SQLite | Integrate | Unblocks accurate IDs, exact pricing keys, set-completion, and the pHash matcher. The keystone fix. |
| **P0** | Resolve identifier output **against the catalog** (validate set/number) | Build | Stops confidently-wrong metadata at the source |
| **P1** | Add **perceptual-hash matcher** (offline, Scryfall/Pokémon images) | Build (OSS technique) | Exact, free, local IDs for top games; cuts Claude-vision spend |
| **P1** | Integrate a **multi-game pricing API** (JustTCG / tcgapi.dev), condition-aware | Integrate | Replaces active-listing proxy with real per-condition prices; satisfies the TradingCardAPI TODO |
| **P2** | **WIA scanner fallback** | Adopt lib | Removes a hard support failure for non-TWAIN devices |
| **P2** | **Slab/cert detection** + 4-subscore grade output | Build/borrow | Recognize already-graded cards; more legible grades |
| **P3** | Roadmap features from OSS comparables (binders, wishlists, portfolio analytics, deck/CSV interop) | Learn | Close the gap with mature collection managers |

---

## 4. Risks & constraints

- **eBay sold comps are effectively unavailable** to indie developers in 2026 (Marketplace
  Insights is partner-gated; Finding API deprecated). Don't build the value model assuming sold
  data from eBay — use a TCG pricing API for real comps.
- **ToS / scraping:** every recommendation above uses official APIs or redistributable bulk
  data, consistent with the "official-APIs-only" stance. Avoid the scraping-based OSS paths.
- **Privacy-first:** the catalog + pHash recommendations are **local-only** and *strengthen*
  the privacy story (fewer cloud calls). A commercial grading/ID API (Ximilar) would mean
  uploading images — only adopt as an optional, opt-in path, not the default.
- **Licensing:** Lorebox is AGPL-3.0 — check license compatibility before vendoring any OSS
  code (Scryfall data is fine to ingest; lifting GPL/unlicensed code into the tree is not).

---

## 5. Sources

**Recognition / OCR / vision:** [tcg-ocr-scanner](https://github.com/starstuffharvestingstarlight/tcg-ocr-scanner) ·
[YamCR](https://github.com/ForOhForError/Yet-Another-Magic-Card-Recognizer) ·
[mtg_card_detector](https://github.com/hj3yoo/mtg_card_detector) ·
[PokeCard-TCG-detector](https://github.com/em4go/PokeCard-TCG-detector) ·
[Moss Machine](https://kairicollections.github.io/Moss-Machines-Magic-the-Gathering-sorting/) ·
[Ximilar identify](https://www.ximilar.com/blog/how-to-scan-and-identify-your-trading-cards-with-ximilar-ai/)

**Catalog / data SDKs:** [Scryfall API](https://scryfall.com/docs/api) ·
[Scrython](https://github.com/NandaScott/Scrython) ·
[Pokémon TCG API](https://github.com/PokemonTCG/pokemon-tcg-api) ·
[TCGdex](https://tcgdex.dev/) · [open-cards](https://codeberg.org/open-cards/open-cards)

**Pricing APIs:** [JustTCG](https://justtcg.com/) · [tcgapi.dev](https://tcgapi.dev/) ·
[TCGdex markets](https://tcgdex.dev/markets-prices) · [TCG Price Lookup](https://tcgpricelookup.com/) ·
[eBay Marketplace Insights thread](https://community.ebay.com/t5/eBay-APIs-Talk-to-your-fellow/Marketplace-Insights-API/td-p/34699452)

**Grading:** [psa_pokemon_cards](https://github.com/crimsonthinker/psa_pokemon_cards) ·
[mint_condition](https://github.com/rthorst/mint_condition) ·
[pokemon-card-analyzer](https://github.com/NickPiscitelli/pokemon-card-analyzer) ·
[Ximilar Card Grading](https://docs.ximilar.com/services/card_grading/)

**Collection managers:** [Spellbook](https://github.com/KyleDerZweite/spellbook) ·
[pokecollector](https://github.com/Git-Romer/pokecollector) ·
[OpenMTG](https://github.com/DredBaron/OpenMTG) ·
[Card-Collection-Manager-2](https://github.com/sebastiandine/Card-Collection-Manager-2)

**MCP servers:** [scryfall-local](https://github.com/findingsimple/scryfall-local) ·
[ptcg-mcp](https://github.com/jlgrimes/ptcg-mcp) ·
[pokemon-tcg-mcp](https://github.com/grzetich/pokemon-tcg-mcp) ·
[mtg-mcp-servers](https://github.com/artillect/mtg-mcp-servers)

**Scanning libs:** [pytwain](https://pytwain.readthedocs.io/) ·
[twain-wia-sane-scanner](https://pypi.org/project/twain-wia-sane-scanner) ·
[wia_scan](https://pypi.org/project/wia_scan/)
