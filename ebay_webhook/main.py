"""
eBay Marketplace Account Deletion Webhook
==========================================
Required by eBay's developer program for all apps using their APIs.

This app uses the Finding API for public sold-listing price data only —
no eBay user data is stored. However eBay still requires a registered
HTTPS endpoint even when opting out of storing user data.

This server:
  1. Responds to eBay's challenge verification (GET request)
  2. Accepts and acknowledges deletion notifications (POST request)
  3. Logs received notifications for audit purposes

Environment variables (set in Render/Railway dashboard or .env):
  EBAY_VERIFICATION_TOKEN  — token you set when registering the endpoint
                             on developer.ebay.com (any random 32+ char string)
  EBAY_ENDPOINT_URL        — the full public URL of THIS endpoint
                             e.g. https://your-app.onrender.com/ebay/deletion

Deploy free on Render:
  1. Push this repo to GitHub
  2. New Web Service → connect repo → set Root Directory to ebay_webhook
  3. Build command: pip install -r requirements.txt
  4. Start command: gunicorn main:app
  5. Add the two env vars above in Render dashboard
  6. Copy the Render URL → register as endpoint on developer.ebay.com
"""

import os
import json
import hashlib
import logging
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify, abort

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

VERIFICATION_TOKEN = os.environ.get("EBAY_VERIFICATION_TOKEN", "")
ENDPOINT_URL       = os.environ.get("EBAY_ENDPOINT_URL", "")

# Simple append-only log of received deletion notifications
LOG_FILE = Path("deletion_notifications.log")


def _challenge_response(challenge_code: str) -> str:
    """
    eBay challenge verification:
    SHA-256( challengeCode + verificationToken + endpointUrl )
    Returns the hex digest.
    """
    payload = challenge_code + VERIFICATION_TOKEN + ENDPOINT_URL
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@app.route("/ebay/deletion", methods=["GET", "POST"])
def ebay_deletion():
    if request.method == "GET":
        # eBay challenge verification
        challenge_code = request.args.get("challenge_code", "")
        if not challenge_code:
            logger.warning("GET /ebay/deletion — missing challenge_code")
            abort(400, "challenge_code required")

        if not VERIFICATION_TOKEN or not ENDPOINT_URL:
            logger.error("EBAY_VERIFICATION_TOKEN or EBAY_ENDPOINT_URL not set")
            abort(500, "Server misconfigured — set env vars")

        response_hash = _challenge_response(challenge_code)
        logger.info("Challenge verification successful: %s…", response_hash[:16])
        # eBay requires exactly this JSON shape
        return jsonify({"challengeResponse": response_hash})

    # POST — actual deletion/closure notification
    try:
        payload = request.get_json(force=True, silent=True) or {}
        notification = payload.get("notification", {})
        topic    = notification.get("topic", "unknown")
        username = payload.get("data", {}).get("username", "unknown")
        user_id  = payload.get("data", {}).get("userId", "unknown")

        logger.info(
            "Deletion notification received — topic=%s  user=%s  id=%s",
            topic, username, user_id
        )

        # Append to audit log
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "received_at": datetime.utcnow().isoformat(),
                "topic":       topic,
                "username":    username,
                "userId":      user_id,
                "raw":         payload,
            }) + "\n")

        # This app stores NO eBay user data, so nothing to delete.
        # Acknowledge with 200 as required by eBay.
        return "", 200

    except Exception as exc:
        logger.exception("Error processing deletion notification: %s", exc)
        # Still return 200 so eBay doesn't keep retrying
        return "", 200


@app.route("/health")
def health():
    """Simple health check for Render."""
    token_set = bool(VERIFICATION_TOKEN)
    url_set   = bool(ENDPOINT_URL)
    return jsonify({
        "status":             "ok",
        "verification_token": "set" if token_set else "MISSING",
        "endpoint_url":       ENDPOINT_URL if url_set else "MISSING",
    })


@app.route("/privacy")
def privacy():
    """Serve the privacy policy (linked from the Microsoft Store listing)."""
    return PRIVACY_HTML, 200, {"Content-Type": "text/html; charset=utf-8"}


PRIVACY_HTML = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Privacy Policy — Lorebox</title>
<style>
 body{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
      max-width:780px;margin:40px auto;padding:0 20px;line-height:1.6;color:#1a1a1a}
 h1{font-size:28px}h2{font-size:20px;margin-top:32px;border-bottom:1px solid #eee;padding-bottom:6px}
 table{border-collapse:collapse;width:100%;margin:12px 0}
 th,td{border:1px solid #ddd;padding:8px 10px;text-align:left;font-size:14px}
 th{background:#f5f5f7}
 .summary{background:#f0f4ff;border-left:4px solid #5865f2;padding:12px 16px;border-radius:4px}
 code{background:#f5f5f7;padding:1px 5px;border-radius:3px;font-size:90%}
 small{color:#666}
</style></head><body>
<h1>Privacy Policy — Lorebox</h1>
<p><small><b>Effective date:</b> June 8, 2026 &nbsp;•&nbsp; <b>Last updated:</b> June 8, 2026</small></p>
<p class="summary"><b>Summary:</b> Your collection lives on your own computer. The
App has no servers and collects no analytics. Card images and card names are sent
to third-party services only to identify and price cards, using API keys you
supply. We do not sell or share your data.</p>

<h2>1. Information stored on your device</h2>
<p>All of the following is stored locally on your computer (under
<code>%APPDATA%\\Lorebox</code>) and is never transmitted to the developer:</p>
<ul>
<li><b>Collection data</b> — card names, sets, numbers, grades, condition scores,
estimated values, purchase prices, quantities, and notes.</li>
<li><b>Card scan images</b> — the front/back images you scan or import.</li>
<li><b>Settings</b> — your preferences, including watch-folder configuration.</li>
<li><b>API keys</b> — your Anthropic and eBay credentials, stored encrypted.</li>
<li><b>Security data</b> — master password stored only as a salted PBKDF2-SHA256
hash; any TOTP secret encrypted; recovery codes hashed. None are reversible.</li>
</ul>
<p>You can delete any of this from within the App, or by deleting the
<code>%APPDATA%\\Lorebox</code> folder.</p>

<h2>2. Information sent to third parties</h2>
<p>The App sends data to these services only to identify and value cards, and only
when you use those features. Because you provide your own API keys, this activity
occurs under your own accounts and is governed by their privacy policies.</p>
<table>
<tr><th>Service</th><th>What is sent</th><th>Purpose</th></tr>
<tr><td>Anthropic (Claude API)</td><td>Images of your cards</td><td>Identify name, set, number, year, game</td></tr>
<tr><td>eBay (Browse API)</td><td>Card name / keywords</td><td>Current market prices</td></tr>
<tr><td>Scryfall</td><td>Card name (Magic cards)</td><td>Magic: The Gathering prices</td></tr>
</table>
<p>Anthropic states that inputs submitted through its API are not used to train its
models. No payment information, account credentials, or personal identifiers are
sent to these services by the App — only card images and card names.</p>

<h2>3. Biometric authentication (Windows Hello)</h2>
<p>If you enable Windows Hello sign-in, your fingerprint/face data is handled
entirely by Windows and never leaves your device. The App only receives a
success/failure result and never sees or stores biometric data.</p>

<h2>4. eBay Marketplace Account Deletion</h2>
<p>The App uses public eBay pricing data only and stores no eBay user account data.
It is registered with a Marketplace Account Deletion/Closure notification endpoint
(<code>/ebay/deletion</code>) which acknowledges such notifications. Because no eBay
user data is stored, no deletion action is required.</p>

<h2>5. Analytics and tracking</h2>
<p>The App contains no analytics, telemetry, advertising, or tracking. The developer
collects no usage data and operates no server that receives your information.</p>

<h2>6. Data sharing and sale</h2>
<p>We do not sell, rent, or share your data. The only outbound data is the card
images and card names you send to the third-party services above.</p>

<h2>7. Children's privacy</h2>
<p>The App is not directed to children under 13 and does not knowingly collect
personal information from them.</p>

<h2>8. Your choices and control</h2>
<ul>
<li>Use the App without API keys — identification/valuation are simply disabled.</li>
<li>Remove or change your API keys at any time in Settings.</li>
<li>Delete individual cards, or your entire local database, from within the App.</li>
<li>Uninstalling and deleting <code>%APPDATA%\\Lorebox</code> removes all local data.</li>
</ul>

<h2>9. Changes to this policy</h2>
<p>We may update this policy as the App evolves; material changes update the
"Last updated" date above.</p>

<h2>10. Contact</h2>
<p>Questions? Contact the developer at: <b>[YOUR-CONTACT-EMAIL]</b></p>

<hr>
<p><small>Lorebox is an independent application and is not affiliated
with, endorsed by, or sponsored by Anthropic, eBay, Scryfall, The
Topps Company, Wizards of the Coast, or any trading card manufacturer.</small></p>
</body></html>"""


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
