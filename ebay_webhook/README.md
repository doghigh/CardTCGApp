# eBay Marketplace Account Deletion Webhook

Required by eBay's developer program. Handles challenge verification and
deletion notifications. This app stores no eBay user data — the endpoint
simply acknowledges notifications.

## Deploy to Render (free)

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your GitHub repo
4. Set **Root Directory** to `ebay_webhook`
5. Build command: `pip install -r requirements.txt`
6. Start command: `gunicorn main:app`
7. Plan: **Free**
8. Add environment variables:
   - `EBAY_VERIFICATION_TOKEN` — a random string you invent (32+ chars, keep it secret)
   - `EBAY_ENDPOINT_URL` — your Render URL + `/ebay/deletion`
     e.g. `https://tcm-ebay-webhook.onrender.com/ebay/deletion`
9. Deploy → copy the URL

## Register on eBay Developer Portal

1. Sign in at [developer.ebay.com](https://developer.ebay.com)
2. **My Account → Application Keys → Production App**
3. Find **Marketplace Account Deletion/Closure Notifications**
4. Enter your endpoint URL: `https://your-app.onrender.com/ebay/deletion`
5. Enter the same `EBAY_VERIFICATION_TOKEN` value
6. Click **Send Test Notification** — eBay will do a challenge GET request
7. If it passes, click **Save**

## Verify it's working

Visit `https://your-app.onrender.com/health` — should return:
```json
{"status": "ok", "verification_token": "set", "endpoint_url": "https://..."}
```

## How it works

**Challenge verification (GET):**
eBay sends `GET /ebay/deletion?challenge_code=abc123`
Server responds with:
```json
{"challengeResponse": "sha256(challengeCode + verificationToken + endpointUrl)"}
```

**Deletion notification (POST):**
eBay sends user deletion data as JSON.
Server logs it and responds `200 OK`.
Since no eBay user data is stored, nothing needs to be deleted.
