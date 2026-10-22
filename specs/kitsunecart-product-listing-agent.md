# Spec: Kitsunecart - autonomous product-listing agent

> **Provenance.** This specification was developed as the standalone
> `kitsunecart` repository and is kept here as a design note. The repository
> has been retired; this document is the surviving artifact.

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
