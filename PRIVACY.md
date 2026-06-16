# Privacy Policy — Lorebox

**Effective date:** June 8, 2026
**Last updated:** June 8, 2026

Lorebox ("the App") is a desktop application for cataloguing,
grading, and valuing trading cards. This policy explains what data the App
handles, where it goes, and the choices you have. Please read it alongside the
privacy policies of the third-party services listed below.

> **Summary:** Your collection lives **on your own computer**. The App has no
> servers and collects no analytics. Card images and card names are sent to
> third-party services **only** to identify and price cards, using **API keys
> you supply**. We do not sell or share your data.

---

## 1. Information stored on your device

All of the following is stored **locally** on your computer (under
`%APPDATA%\Lorebox`) and is never transmitted to the developer:

- **Collection data** — card names, sets, card numbers, grades, condition
  scores, estimated values, purchase prices, quantities, and notes you add.
- **Card scan images** — the front/back images you scan or import.
- **Settings** — your preferences, including the watch-folder configuration.
- **API keys** — your Anthropic and eBay credentials, stored **encrypted**
  (AES via the `cryptography` library) so they are not kept in plain text.
- **Security data** — your master password is stored only as a salted
  PBKDF2-SHA256 hash; any TOTP two-factor secret is encrypted; recovery codes
  are stored as hashes. None of these can be reversed to recover the original.

You can delete any of this at any time from within the App, or by deleting the
`%APPDATA%\Lorebox` folder.

## 2. Information sent to third parties

The App sends data to the following services **only** to perform card
identification and valuation, and only when you use those features. Because you
provide your own API keys, this activity occurs under **your own accounts** with
those providers and is governed by their privacy policies.

| Service | What is sent | Purpose |
|---------|--------------|---------|
| **Anthropic (Claude API)** | Images of your cards | Identify the card's name, set, number, year, and game |
| **eBay (Browse API)** | Card name / search keywords | Fetch current market prices |
| **Scryfall** | Card name (Magic cards) | Fetch Magic: The Gathering prices |

- Anthropic states that inputs submitted through its API are **not used to
  train its models**. See Anthropic's Privacy Policy.
- No payment information, account credentials, or personal identifiers are sent
  to any of these services by the App — only card images and card names.

## 3. Biometric authentication (Windows Hello)

If you enable Windows Hello sign-in, your fingerprint/face data is handled
entirely by **Windows** and never leaves your device. The App only receives a
success or failure result; it never sees or stores biometric data.

## 4. eBay Marketplace Account Deletion

The App uses public eBay pricing data only and **stores no eBay user account
data**. In accordance with eBay's developer requirements, the App is registered
with a Marketplace Account Deletion/Closure notification endpoint
(`https://cardtcgapp.onrender.com/ebay/deletion`), which acknowledges such
notifications. Because no eBay user data is stored, no deletion action is
required.

## 5. Analytics and tracking

The App contains **no analytics, telemetry, advertising, or tracking** of any
kind. The developer does not collect usage data and has no server that receives
your information.

## 6. Data sharing and sale

We do **not** sell, rent, or share your data. The only outbound data is the
card images and card names you send to the third-party services above, which
you control through your own API keys and use of the valuation features.

## 7. Children's privacy & parental involvement

The App is not directed to children under 13 and does not knowingly collect
personal information from them. Because the App stores a collection locally and
opens without a login by default, **we encourage a parent or guardian to be
involved when the collector is under 16** — setting up the App alongside them
and approving its use without a login. The App shows a one-time notice to this
effect on first launch.

## 8. Your choices and control

- Use the App without API keys — card identification and valuation are simply
  disabled; the rest of the App still works.
- Remove or change your API keys at any time in **Settings**.
- Delete individual cards, or your entire local database, from within the App.
- Uninstalling the App and deleting `%APPDATA%\Lorebox` removes all
  locally stored data.

## 9. Changes to this policy

We may update this policy as the App evolves. Material changes will be reflected
by an updated "Last updated" date above.

## 10. Contact

Questions about this policy? Contact the developer at:
**[YOUR-CONTACT-EMAIL]**

---

*Lorebox is an independent application and is not affiliated with,
endorsed by, or sponsored by Anthropic, eBay, Scryfall, The Topps
Company, Wizards of the Coast, or any trading card manufacturer.*
