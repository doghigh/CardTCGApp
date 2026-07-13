import { monthKey, isOverCap } from './cap.js';

const ANTHROPIC_URL = 'https://api.anthropic.com/v1/messages';
const ANTHROPIC_VERSION = '2023-06-01';

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method !== 'POST' || url.pathname !== '/v1/messages') {
      return json(404, { type: 'error', error: { type: 'not_found', message: 'not found' } });
    }

    const cap = parseInt(env.MONTHLY_TRIAL_CAP, 10);
    if (!Number.isFinite(cap)) {
      return json(503, { type: 'error', error: { type: 'misconfigured', message: 'Trial cap not configured.' } });
    }
    const key = monthKey(new Date());
    const count = parseInt((await env.TRIAL_KV.get(key)) || '0', 10);

    if (isOverCap(count, cap)) {
      return json(429, {
        type: 'error',
        error: { type: 'trial_capacity', message: 'Free trial is at capacity this month.' },
      });
    }

    // Relay the request body verbatim, injecting the developer's key.
    const body = await request.text();
    const upstream = await fetch(ANTHROPIC_URL, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-api-key': env.ANTHROPIC_API_KEY,
        'anthropic-version': ANTHROPIC_VERSION,
      },
      body,
    });

    // Count only confirmed successes. KV is eventually consistent; acceptable
    // for a coarse monthly $ cap.
    if (upstream.ok) {
      await env.TRIAL_KV.put(key, String(count + 1));
    }

    // Pass the upstream response straight back. No payload logging anywhere.
    return new Response(upstream.body, {
      status: upstream.status,
      headers: { 'content-type': upstream.headers.get('content-type') || 'application/json' },
    });
  },
};

function json(status, obj) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}
