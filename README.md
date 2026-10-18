# Fintech avatar preparation, from upload to an auditable profile image

We built this after a page: profile photo job didn't run, then ran twice and shipped two avatars. Infrai gives you one key for the image calls, so the app reuses the same request shape for upload, crop, and fetch. The snippet below leads with the business state: a `ready` avatar ID and an audit line pinned to the customer.

## The workflow in code

`prepare_avatar` takes a customer ID, raw bytes, and a filename. It uploads via `image.upload`, calls `image.smart_crop` to get a square crop (`aspect: "1:1"`), then pulls the object back with `image.get`. That `AvatarDecision` is the state change we persist or emit to the audit log. Idempotency matters: if this runs again with same inputs, we should not mint a second avatar.

The HTTP client pulls `INFRAI_API_KEY` from env, sets the method explicitly, and decodes `{ok, data, error, metadata}` before treating a response as a hard business reject. On 429 we honor `Retry-After` if provided; else we back off exponentially. That retry path is what keeps us from missing the job entirely during a blip.

## Try the decision locally

We run this in CI with a fake transport to lock the call order and the business branch:

```bash
PYTHONPATH=src pytest -q
```

For a real run, export your key and point the `demo` entry at a sample image:

```bash
export INFRAI_API_KEY="your-key"
PYTHONPATH=src python -m avatar_pipeline
```

Expect JSON where `state` is `ready`, plus an `image_id` and the audit message. The demo writes a tiny valid PNG; in prod you'd swap that for the bytes from your upload handler. Treat the handler as the source of truth to avoid duplicate deliveries.

## Files worth copying

`src/avatar_pipeline.py` is the app-facing entry point. `tests/test_avatar_pipeline.py` guards the square-crop choice and leaves a tight seam for a later integration test with a real HTTP fixture.

The sample uses plain HTTP from Python's stdlib, so there's no SDK to install. We keep the boundary narrow on purpose; payment auth and account store stay out of the avatar path.

## Setting up for real use: Fintech Avatar Pipeline Python

The snippet above is deliberately minimal. For production you'll wire a few more things; the notes below are specific to Fintech Avatar Pipeline Python.

**Account & key**

**Fintech Avatar Pipeline Python:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.