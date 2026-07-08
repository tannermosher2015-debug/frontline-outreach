# Build Queue Runbook (stage 4 of the autonomous funnel)

Turn each `interested` lead into a deployed, noindex demo site, then hand off to
the sample sender. This is the one stage a Claude agent runs, because it uses the
`business-recon` and `build-website` skills. Everything it produces follows the
standing rules: WCAG 2.1 AA, semantic landmarks, real facts only, no em dash,
placeholders marked clearly, verified before deploy.

## When to run
- Now, supervised: open `claude` in this repo and say "work the build queue".
- Scheduled later (once the host is chosen): headless, e.g.
  `claude -p "Follow BUILD_QUEUE.md and work the build queue."`

## Steps
1. List the queue: `python -m outreach queue`.
   Each line is `place_id  name | category, town | site`.
2. For each lead:
   a. **Recon** with the `business-recon` skill: gather real services, hours,
      contact, brand colors, and reusable photos. Use only facts from the
      business's own sources (see memory `feedback-client-site-facts-first`).
   b. **Confidence gate.** If there is not enough real material to make a
      genuinely good sample (no usable services or photos or contact, or the
      business looks closed), STOP for this lead. Do not build a weak sample.
      Leave it `interested` and note it for Tanner. A bad sample sent
      automatically is worse than sending nothing.
   c. **Build** with the `build-website` skill from the recon brief. Single file,
      its own design (fonts, colors, hero declared up front). Never invent a
      phone, email, or price: mark any unknown as a clear placeholder.
   d. **noindex.** This is an unsolicited sample, so add both the `noindex` meta
      tag and the `X-Robots-Tag` (same as the holu and keokea demos). It must
      not get indexed.
   e. **Deploy** to `<slug>.frontlinewebdesign.tech` via the Hostinger MCP
      (create subdomain, deploy the static file). Slug = business name,
      lowercased, no spaces.
   f. **Verify before recording:** run the Playwright desktop and mobile shots
      and read both; run `impeccable detect` if available and fix findings.
      Do not record a URL you have not looked at.
   g. **Record:** `python -m outreach set-sample <place_id> https://<slug>.frontlinewebdesign.tech`.
3. When the queue is clear: `python -m outreach send-samples`.
   Writes `.eml` files in dry-run; emails for real only when `send_mode = "live"`.

## Never
- Never email a sample that shows a placeholder phone, email, or price as if real.
- Never skip the noindex on a sample.
- Never build for a lead that opted out or is already `sample_sent`.
