# Bricks recognition API

Production: `https://bricks-recognition.uurraa.workers.dev/recognize`

The GitHub Pages client calls this Worker. Cloudflare Workers AI runs Gemma 4 Vision via the `AI` binding; no Claude/OpenAI key is needed. Usage is billed or deducted from the Cloudflare account's Workers AI allowance, not a child's device. This is an anonymous, rate-limited family application, not an authenticated commercial API.

## Run and deploy

```sh
npm ci
npm test
npm run types
npx wrangler deploy --dry-run
npm run deploy
```

`wrangler login` must have access to the configured account and Workers AI. Local `wrangler dev` can invoke the remote AI binding and consume quota. Do not commit secrets, photos, or `.dev.vars`. After deploying to another account, update the client endpoint in `app/bricks.html`.

## Contract

`POST /recognize`, JSON `{ "image": "<base64>", "mime": "image/jpeg" }`. PNG and WebP are also accepted. The request must have `Origin: https://pllato.github.io`. A successful response is `{ "items": [{ "color": "red", "size": "2x4", "count": 1 }], "note": "…" }`. Empty `items` means no supported bricks could be confidently identified; it must never be replaced with invented inventory.

Errors are JSON `{ "error": "code" }`. Invalid input: 400/413/415; disallowed origin: 403; throttling: 429; malformed model response: 502; provider unavailable: 503. The client displays local, child-friendly messages, never raw provider errors. `GET /health` checks the Worker, not model availability.

The Worker bounds the streamed request body to 4 MB, checks image signatures, validates every returned item, rejects truncated responses, aggregates duplicates, and rejects counts above 99. It neither stores photographs nor logs request bodies/model content. Cloudflare processes the image to perform inference.

Limits are 4 requests/minute per IP and 20 requests/minute overall **per Cloudflare location**. Shared Wi-Fi users share the IP limit. CORS is not authentication; a non-browser client can forge Origin. These rate limits are not a hard global spending cap. For a public launch, add authenticated sessions and an account-wide budget before increasing limits.

## Validation on 2026-09-29

- Node tests cover the real handler with a mocked AI binding: valid/empty results, duplicates, malformed/truncated responses, CORS/preflight, limits, oversized/invalid images, and provider failure sanitization.
- Real Worker + Workers AI call on the user's authorized screenshot: HTTP 200 in about 10 seconds, empty inventory. The cluttered photograph contains many unsupported special pieces. This establishes connectivity only, not counting accuracy.
- Browser checks cover file compression, old-key removal with inventory preservation, success/apply, empty result, rate limit, malformed result, offline behavior, repeated clicks and changing the photo during recognition.

Recognition is approximate and supports full-height rectangular bricks only. Always verify the pieces needed for a chosen model. No claim of accuracy on arbitrary piles is made.
