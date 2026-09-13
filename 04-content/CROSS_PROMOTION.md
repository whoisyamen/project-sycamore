# Content & cross-promotion protocol — Project Sycamore

How Operation SM's short-form output and the site feed each other, plus curation rules for what appears on the wall. Applies all editorial/security policy from `../operation-sm/00-admin/` by reference (evidence-based, nonpartisan, defensive framing; attribution uncertainty stated explicitly).

## Curation rules for the live dashboard

1. **Every item links to its primary source.** Headline + one-line context only — no full-article mirroring (copyright hygiene per security policy section 4).
2. **Attribution confidence is visible**: items from a single outlet carry an "unconfirmed" marker; multi-outlet corroboration upgrades the badge automatically in the pipeline, never by hand.
3. **No partisan framing** — same standard as video scripts: state what happened and who claims it, not whose side it favors.
4. **Board membership is data-driven**: events land on boards (country/topic) via tags from the ingest classifier; human curation only removes false positives, never cherry-picks for narrative effect.
5. Stale or broken items age out automatically per board TTLs defined in the pipeline config — no manual pruning required to keep the wall honest.

## Cross-promotion loop

    Operation SM video (approved channel post)
        |   CTA: "See it live on the wall" -> /board/<slug> or event page
        v
     Sycamore site board/event page
        |   footer/header CTAs back to approved social channels + daily briefing signup (G4)
        v
  viewer re-engagement; new video references trending boards ("what happened in X overnight")

- Each published short gets a **deep link** chosen at publish time: the specific board or event page, never the bare homepage.
- Social posts are approval-gated per Operation SM standing rules — nothing auto-posts from either side of this loop without Lord Yams's sign-off.
- The daily briefing email (G4) is itself a cross-promotion asset: its subject line mirrors that day's Signal Brief video hook where the story matches, so both channels reinforce each other.

## Measurement (ties to Operation SM analytics framework)

Tracked per gate review in `../operation-sm/08-analytics/`: site sessions by source channel, board-level dwell time and click-through-to-source rate, social post to site conversion, returning-visitor share. These are the inputs for pricing experiments at G4.
