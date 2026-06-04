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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
