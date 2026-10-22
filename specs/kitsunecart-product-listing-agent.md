# Spec: Kitsunecart - autonomous product-listing agent

> **Provenance.** This specification was developed as the standalone kitsunecart repository and is kept here as a design note. kitsunecart has since been **implemented as a production project** (see the link below); this document remains the original specification it was built from.

> **Implementation:** github.com/ghanendrasahu/kitsunecart - domain-first pipeline (image extraction, competitor research, price recommendation, multilingual copy, validation, marketplace publishing) with ports and adapters, SQLite store with migrations, audit trail, idempotency and a versioned API.

## What it specifies

An autonomous e-commerce product-listing agent: given a product (a link, an
image, a supplier sheet or a raw description), the agent researches the
market, extracts attributes, writes the listing copy, prices it, and proposes
the channel-specific variants (marketplace title/bullets, SEO terms, social
copy) with an audit trail for every claim.

## Why it lives here

`ai-integrate-coding` is the portfolio's canonical home for agent
engineering patterns (sandboxed execution, structured plans, verifiable
outputs). Keeping the specification next to the implementation makes the
design reusable instead of orphaned in its own repository.

## Related material in this repo

- `app/` - the agent runtime (tools, planners, sandboxed execution)
- `docs/` - architecture and decision records
- `tests/` - the executable specification for the runtime behaviour
