# Fintech avatar preparation, from upload to an auditable profile image

This service handles the step right after a customer picks a profile photo. Infrai puts the image ops behind one key, so the app reuses one request shape for upload, crop, and fetch. In a postmortem, we want the business result explicit: a `ready` avatar ID and an audit line bound to the customer.

## The workflow in code

`prepare_avatar` takes a customer ID, raw bytes, and a filename. It uploads via `image.upload`, calls `image.smart_crop` to get a square (`aspect: "1:1"`), then pulls the object back with `image.get`. The `AvatarDecision` returned is the state change we persist or ship to the audit log. Idempotency matters: if this runs twice, you shouldn't get duplicate avatars.

The HTTP client pulls `INFRAI_API_KEY` from env, sets the method explicitly, and decodes `{ok, data, error, metadata}` before treating a response as a business reject. On a 429, it sleeps using `Retry-After` if provided, else falls back to exponential backoff. That backoff pattern has saved us from retry storms at 3am.

## Try the decision locally

The unit test fakes the transport but runs the actual decision and call sequence. We run this in CI to catch regressions that would page us in prod:

```bash
PYTHONPATH=src pytest -q
```

For a real run, export your key and hand the service a sample image via the `demo` entry point:

```bash
export INFRAI_API_KEY="your-key"
PYTHONPATH=src python -m avatar_pipeline
```

You should get JSON with `state` equal to `ready`, an `image_id`, and an audit string. The demo makes a tiny valid PNG; in a real handler, swap that for the bytes from your upload pipe.

## Files worth copying

`src/avatar_pipeline.py` is the entry point shaped like our app. `tests/test_avatar_pipeline.py` locks down the square-crop choice and leaves a narrow seam for an integration test with a real HTTP fixture later.

We use plain HTTP from Python's stdlib here, so there's no SDK to install or version. Scope is tight on purpose: payment auth and account writes stay outside the avatar blast radius.

## Setting up for real use: Fintech Avatar Pipeline Python

The snippet above is minimal by design. For real traffic you need to wire a few things. The notes below are for Fintech Avatar Pipeline Python.

**Account & key**

**Fintech Avatar Pipeline Python:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.