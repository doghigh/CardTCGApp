# LoreBox Marketing Plan

## Executive Summary

LoreBox is a privacy-first Windows desktop application for managing personal trading card collections. It differentiates itself from cloud-based competitors by keeping all data local — no accounts, no subscriptions, no tracking. This plan outlines how to reach collectors, build community trust, and grow downloads on the Microsoft Store.

---

## Product Snapshot

| Attribute | Detail |
|-----------|--------|
| Platform | Windows desktop (Microsoft Store) |
| Price | Free (BYOK — bring your own API keys) |
| License | AGPL-3.0 open source |
| Core Value | Full-featured card management, fully offline |
| AI Features | Claude vision for card ID & condition grading |
| Supported Games | Magic: The Gathering, Pokémon, sports cards, other TCGs |
| Current Version | 1.1.1.0 |

---

## Target Audience

### Primary: The Privacy-Conscious Collector
- Age 25–45, owns 500+ cards
- Distrustful of SaaS tools that monetize collection data
- Comfortable managing their own API keys
- Likely already using spreadsheets or a combination of apps

### Secondary: The Serious Grader
- Grading-prep hobbyist sending cards to PSA/BGS/CGC
- Needs consistent, documented condition assessments before submission
- Values repeatability and local record-keeping

### Tertiary: The Bulk Organizer
- Acquired large lots (estate sales, storage unit finds, store buyouts)
- Needs batch import and duplicate detection at scale
- Less interested in AI features, more in speed and CSV export

---

## Competitive Landscape

| Competitor | Cloud | Subscription | Privacy | AI ID |
|------------|-------|--------------|---------|-------|
| Collector Vaults | Yes | Yes | No | No |
| TCGplayer Collection | Yes | Freemium | No | No |
| Delver Lens | Yes | Yes | Partial | Yes |
| Card Conjurer | Yes | No | No | No |
| **LoreBox** | **No** | **No** | **Yes** | **Yes** |

**Core message:** LoreBox is the only serious collection manager that is 100% local, 100% free, and AI-powered.

---

## Marketing Goals (12-Month)

1. **500 Microsoft Store downloads** within 90 days of the v1.1.1.0 release
2. **2,000 total downloads** by end of year 1
3. **100 GitHub stars** within 6 months
4. **Active community** of 200+ members across Reddit/Discord
5. **3+ content creator features** (YouTube, podcast, blog)

---

## Positioning & Messaging

### Tagline
> **"Your collection. Your computer. Your rules."**

### Supporting Messages
- "No account required. No subscription. No cloud."
- "AI-powered card identification — without sending your cards anywhere."
- "From scanner to searchable inventory in seconds."
- "Built for collectors who take privacy as seriously as condition grades."

### Tone
Honest, technically confident, community-first. Avoid over-promising. Lean into the open-source credibility.

---

## Channels & Tactics

### 1. Reddit (Priority: High)

**Target subreddits:**
- r/magicTCG (~800k members)
- r/pkmntcg (~600k members)
- r/SportsCardCollectors (~200k members)
- r/Gameboy (niche cross-sell opportunity for retro collectors)
- r/homelab (privacy-tech angle)
- r/selfhosted (BYOK, local-first angle)

**Tactics:**
- Weekly value posts: share condition grading tips, collection organization guides — no direct promotion until credibility is established
- Submit to r/selfhosted and r/homelab with the privacy/local-first angle
- AMA-style post: "I built a local-only card manager with AI grading — happy to answer questions"
- Respond genuinely to posts asking for collection management recommendations

**Do not:** post identical promotional content across subreddits — each community detects this immediately and it destroys trust.

---

### 2. GitHub (Priority: High)

**Why:** AGPL-3.0 open source means the GitHub repo is itself a marketing asset.

**Tactics:**
- Polish the README with a 60-second GIF demo of scan → identified card → graded
- Add badges: Microsoft Store download link, license, version
- Respond to all issues within 48 hours — fast response is a strong signal to potential contributors and users evaluating the project
- Tag issues `good first issue` to invite contributions
- Write a CONTRIBUTING.md that makes it easy to add support for new card games/sets
- Submit to "awesome-selfhosted" list (local-first software directory with high traffic)

---

### 3. YouTube / Content Creators (Priority: Medium)

**Target creator profiles:**
- TCG pack-opening channels (1k–100k subscribers)
- Card grading prep channels
- Privacy-tech / FOSS / self-hosted channels

**Approach:**
- Reach out directly with a pre-built demo video they can embed or reference
- Offer to provide a detailed written overview they can use for their own script
- No payment required — the FOSS angle and novelty of AI-powered local card ID is genuinely interesting content
- Prioritize creators who already discuss grading prep — they have the exact audience that cares about condition assessment

---

### 4. Microsoft Store Optimization (Priority: High)

The Store listing is the bottom of the funnel — optimize it first.

**Actions:**
- Screenshots: show the most impressive feature first (scanner → AI card identification in one flow)
- Description: lead with the privacy angle in the first sentence; most Store listings bury their value proposition
- Keywords: include "card manager," "TCG collection," "Pokémon cards," "Magic the Gathering," "sports card tracker," "card grader"
- Actively respond to all Store reviews — reviewers and potential users read the responses
- Request reviews in-app at a natural moment (e.g., after first successful batch import)

---

### 5. Discord Communities (Priority: Medium)

**Target servers:**
- The Mana Drain (competitive Magic)
- PTCGOne (Pokémon TCG)
- Various sports card Discord servers
- Self-Hosted / FOSS communities (r/selfhosted has a companion Discord)

**Tactics:**
- Participate genuinely for 2–4 weeks before mentioning LoreBox
- Share the tool when someone asks about collection management — not as a broadcast
- Offer to demo live in a voice channel to interested members

---

### 6. Blog / Dev Log (Priority: Low–Medium)

A short development blog (GitHub Pages or similar) serves two purposes: SEO and credibility.

**Post ideas:**
- "Why I built a local-first card manager instead of another SaaS app" — resonates with privacy and FOSS communities
- "How we use Claude vision API to grade card condition" — technical audience
- "Scanning 1,000 cards in an afternoon: a batch import walkthrough"
- "The math behind condition-adjusted market value"

---

## Launch Campaign (90-Day Plan)

### Week 1–2: Foundation
- [ ] Polish GitHub README with demo GIF and Store badge
- [ ] Optimize Microsoft Store listing (screenshots, description, keywords)
- [ ] Submit to awesome-selfhosted
- [ ] Create a short (90-second) screen-recorded demo video

### Week 3–4: Seeding
- [ ] Post to r/selfhosted and r/homelab
- [ ] Begin participating in TCG subreddits (no promotion yet)
- [ ] Identify 10 relevant YouTube creators and draft outreach emails
- [ ] Create a GitHub Discussions space for community Q&A

### Week 5–8: Community
- [ ] Post the AMA thread in the most relevant subreddit
- [ ] Send outreach to 10 YouTube creators
- [ ] Engage daily in Discord communities where the tool has been mentioned
- [ ] Publish first dev blog post

### Week 9–12: Momentum
- [ ] Follow up with YouTube outreach
- [ ] Publish second dev blog post (technical grading deep-dive)
- [ ] Post to r/magicTCG and r/pkmntcg with genuine value content (not ads)
- [ ] Assess download metrics and adjust

---

## Metrics & Success Criteria

| Metric | 30-Day | 90-Day | 12-Month |
|--------|--------|--------|----------|
| Microsoft Store downloads | 100 | 500 | 2,000 |
| GitHub stars | 20 | 60 | 150 |
| GitHub issues/discussions | 5 | 20 | 60 |
| Community members (Reddit mentions + Discord) | — | 100 | 300 |
| 4–5 star Store reviews | 5 | 25 | 80 |

---

## Budget Estimate

LoreBox is a one-person FOSS project. This plan is designed to be **$0 cash outlay** — all tactics rely on earned media, community engagement, and creator outreach rather than paid advertising.

| Activity | Cost |
|----------|------|
| Reddit, Discord, GitHub engagement | $0 (time) |
| Creator outreach | $0 (time) |
| Microsoft Store listing | $19 one-time (already paid) |
| Blog/website hosting | $0 (GitHub Pages) |
| Demo video production | $0 (screen recording) |
| **Total** | **$0** |

If budget becomes available, the highest-ROI paid option would be **Reddit promoted posts** in r/magicTCG or r/pkmntcg targeted to active collectors (~$200–500 for a test campaign).

---

## Key Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Low discoverability in Microsoft Store | Invest in Store ASO (keywords, screenshots) and external backlinks |
| Community skepticism toward self-promotion | Lead with value content; be transparent that you built it |
| API key setup friction deters new users | Write a first-run wizard and a plain-English setup guide |
| Competitor launches a local-first version | Double down on open source credibility and community relationships |
| Privacy claims not believed | Publish technical architecture doc proving no data leaves the device |

---

## Summary

LoreBox's marketing advantage is its honesty: it genuinely does something no competitor does (local-first, AI-powered, free). The plan prioritizes **community trust over volume** — building genuine relationships in TCG communities before asking for anything. The Microsoft Store and GitHub are the two distribution channels that matter most; both should be polished before any outreach begins.

The 90-day campaign is achievable with ~5 hours per week of community engagement and roughly 2–3 hours per week of content work. Success is measured by downloads and community size, not vanity metrics.
