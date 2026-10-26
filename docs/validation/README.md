# Current validation evidence

| Evidence | Scope |
| [Acceptance and release review](2026-10-26-acceptance/README.md) | Final source/privacy/dependency audit, retained application checks and explicit acceptance limits |
| --- | --- |
| [Fresh README walkthrough](2026-10-26-documentation/README.md) | Current documentation, clean locked installs, literal demo/API checks, diagram/media and teardown evidence |
| [Measured evaluation and review](2026-10-26-evaluation/README.md) | Frozen method, all nine OpenAI attempts, reproducible scores/latencies, qualitative review, versions, failures and final audit |
| [Real browser media](../media/2026-10-26/README.md) | Desktop/mobile screenshots, original recordings, captioned video and descriptive transcript |
| [Functional validation](2026-10-25-functional/review.md) | Deployed scenarios, exact concurrent windows, controlled failures, real outage/recovery and enabled/disabled tracing |
| [Full-stack validation](2026-10-25-full-stack/review.md) | Locked installs, images, seeded Compose operation and teardown |
| [Frontend interaction](2026-10-25-feature-interaction/review.md) | Controlled report/error/timeout, keyboard, responsive and zoom checks |

Each record defines its tested scope, source revision, commands and limitations.
Synthetic service mentions are not proven root-cause accuracy. Controlled
fixtures, paid model calls and browser timings are identified separately.

Superseded baseline and transition snapshots through October 24 were retired
intact from the working tree on October 26. They are preserved in Git at
`5ecad6f`. Incoming guide links to those snapshots now point to their original
immutable Git revision. No old measurement was renamed, edited or promoted as a
new result. Current functional/interaction/full-stack records remain, including
their failures. The [retirement manifest](2026-10-26-evaluation/retirement.json)
records the scope and counts; the deletion diff identifies each retired path.
Git history was not rewritten.

For a stalled asyncio/thread check, use the [independent diagnostic](diagnostics.md)
before changing graph behavior. The diagnostic is independent of the application.

The acceptance audit subsequently retired 39 whole transition logs/JSON artifacts
from the October 25–26 records. Their original bytes remain at the revision in
the [additional retirement manifest](2026-10-26-acceptance/retirement.json).
Affected guide links resolve to immutable Git objects. Historical audit scripts
retain their original assumptions and are reproduction records for those revisions.
