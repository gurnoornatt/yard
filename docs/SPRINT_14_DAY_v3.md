# 14-Day Sprint v3 — Sentinel Validation + First Client (2026-Compliant Edition)

**Goal:** Contract signed by Day 14, money wired ideally by Day 14, otherwise Day 21.

**The hard truth this version corrects:** Cold-emailing from a new domain on Day 2 will get the domain burned within a week per 2026 deliverability standards (Google, Yahoo, Microsoft enforcement tightened Feb 2024–May 2025). A new domain MUST warm for 14-21 days before the first cold send. v2 had this wrong.

**The fix:** Run two email tracks in parallel.
- **Track 1 (immediate):** Cold sends from your existing personal email (Gmail or USF .edu) — your established reputation lets you send 5/day from Day 1 without burning a new domain. This is what gets the first 5 cold messages out tomorrow morning.
- **Track 2 (background):** Buy a SECONDARY domain Day 1 (NOT your main one), set up Google Workspace, configure SPF/DKIM/DMARC, start Instantly or Smartlead warmup. By Day 15-21, the warmed domain is ready for production cold sending.

This is how serious cold-email operators run in 2026. You do NOT cold-email from a brand new domain.

**Three parallel tracks every day from Day 2:**
- **Track A — Sentinel validation:** Reliability, accuracy, usefulness gates
- **Track B — Cold outreach:** 5/day from established email, working the pipeline
- **Track C — Infrastructure + content:** Landing page, drip, content engine, secondary domain warmup, RB2B, etc.

**Intensity:** 14-16 hour days. Eat real meals. Sleep 6+ hours.

---

## Day 1 — Infrastructure foundation (full day, no cold sends)

The single most important constraint: by EOD you must have a secondary domain registered, Google Workspace configured, SPF/DKIM/DMARC published, and warmup started. The 14-day clock on warmup starts today. Every hour delayed = first warmed-domain send delayed.

### Morning Block 1 — Domain + DNS Foundation (~3 hours)

- [ ] Pick a primary brand domain (e.g., `<yourbrand>.com`). Used for landing page, marketing, public identity.
- [ ] Pick a secondary outbound domain (e.g., `try<yourbrand>.com`, `get<yourbrand>.com`, `<yourbrand>-mail.com`). Used ONLY for cold email after warmup. **Do not skip this — sending cold from your main domain in 2026 will burn it within 30 days.**
- [ ] Buy both domains. Cloudflare or Namecheap. Around $24 total.
- [ ] Move DNS management to Cloudflare for both (regardless of registrar). Cloudflare > registrar DNS panels for cold-email work in 2026.
- [ ] Set up Google Workspace on the secondary outbound domain ($7/mo). Create `gurnoor@try<yourbrand>.com`.
- [ ] Set up Google Workspace on the primary domain ($7/mo more) for `gurnoor@<yourbrand>.com` — this is for client communication, transactional emails, official identity. NOT for cold sends.
- [ ] Configure DNS records on BOTH domains (in Cloudflare):
  - **MX record** pointing to Google Workspace (`smtp.google.com` priority 1, etc.)
  - **SPF record** as TXT: `v=spf1 include:_spf.google.com ~all` (use `~all` soft fail, not `-all` hard fail — `-all` causes legitimate emails to fail in some configurations)
  - **DKIM record:** Google Workspace Admin Console → Apps → Google Workspace → Gmail → Authenticate email → Generate new DKIM key (2048-bit). Publish the resulting TXT record at `google._domainkey.yourdomain.com`. Activate DKIM in admin console AFTER record propagates (verify with MXToolbox).
  - **DMARC record** as TXT at `_dmarc.yourdomain.com`: `v=DMARC1; p=none; rua=mailto:dmarc@yourdomain.com; aspf=s; adkim=s` — start at `p=none` for 30 days, then move to `p=quarantine`. Never start at `p=reject`.
- [ ] Verify all three records pass at MXToolbox.com for both domains
- [ ] Test deliverability: send a manual email from each Google Workspace account to your personal Gmail, Outlook, Yahoo. Verify they land in inbox (allow 30 min for DNS propagation if any go to spam)

### Morning Block 2 — Cold email warmup setup (~1.5 hours)

This is the background task. It runs for 14-21 days while everything else happens.

- [ ] Sign up for Instantly (~$37/mo) OR Smartlead (~$39/mo) — either works, both include warmup pools. Smartlead has unlimited mailboxes on lower tiers if you want to scale.
- [ ] Connect `gurnoor@try<yourbrand>.com` (secondary outbound) to the warmup tool
- [ ] Configure warmup settings:
  - Start at 5 emails per day
  - Ramp by 3-5 emails per day
  - Cap at 30 emails per day total (DO NOT exceed — Google throttles bulk senders)
  - Spread across 8-12 hour windows
  - Use the tool's default warmup pool (Smartlead Premium or Instantly's pool — both trusted)
- [ ] **Do NOT touch this until Day 15.** Let it ramp.
- [ ] Optional: also connect `gurnoor@<yourbrand>.com` (primary) to warmup at a lower volume (5/day cap) just to build trust on that domain for future client communication. Not for cold outreach ever.

### Afternoon Block 1 — Other accounts and APIs (~1.5 hours)

- [ ] Anthropic API: $20 credit added
- [ ] Supabase: new project, save connection string and anon key
- [ ] Resend: account, verify the primary domain (NOT the secondary outbound domain — Resend is for transactional/inbound, not cold)
- [ ] Cal.com: free account, create "Discovery Call - 30 min" with intake fields (firm name, submarket, OM to analyze before call)
- [ ] RB2B: free account (150 person-level credits/mo). Match rate for US traffic: 8-15% person-level, 40-55% company-level per 2026 benchmarks. Good enough for our scale.
- [ ] HubSpot CRM Free: configure 10-stage pipeline (New Lead → Contacted → Replied → OM Forwarded → Discovery Booked → Discovery Done → Proposal Sent → Contract Signed → Deposit Paid → Active Client)
- [ ] Stripe: 3 payment links — $5K setup, $4K/mo recurring subscription, $500 OM overage
- [ ] Slack: workspace with 12 channels per master plan
- [ ] GitHub: public repo `sentinel` (clean up hackathon code, add good README, link to landing page)

### Afternoon Block 2 — Landing Page (~4 hours)

The 2026 landing page standard: 5-second clarity test, headline under 44 characters (8 words max), one primary CTA above fold, form ≤5 fields, load under 3 seconds, mobile-first.

- [ ] Open v0 (https://v0.dev) or Cursor. Build single-page Next.js, deploy to Vercel under primary domain.
- [ ] Hero section (above fold):
  - **Eyebrow:** "MULTIFAMILY ACQUISITION DECISION SUPPORT"
  - **H1 (under 44 chars):** "Your analyst, supercharged."
  - **Sub-headline:** "I cut public-records due diligence on multifamily broker OMs from 3 hours to 5 minutes. Forward me any OM to test it free."
  - **Primary CTA above fold:** "Get free OM analysis" → opens email form (3 fields: email, firm name, target submarket)
  - **Secondary CTA:** "Book a 20-min call" → Cal.com embed
  - **Trust indicators near CTA:** "Open-source methodology" badge + GitHub link, "Built by GTM engineer (ex-Revyl, YC W24)" line
- [ ] Section 2 — The problem (2 short paragraphs):
  - Managing partners get 30-50 broker OMs per month. Each takes 2-3 hours of analyst time on public records before underwriting even starts. Most are noise.
  - The bottleneck isn't deal flow. It's triage. Your analyst's hours are the constraint.
- [ ] Section 3 — How it works (3 cards):
  - 1. Forward an OM to gurnoor@<yourbrand>.com
  - 2. AI agent runs 10-step due diligence: ownership chain, loan maturity, comps, permits, code violations, tax delinquency
  - 3. Structured pursue/watchlist/pass analysis back same day
- [ ] Section 4 — What's analyzed (6 cards): each with icon and 1-sentence description
- [ ] Section 5 — Proof:
  - Link to GitHub repo (open-source signal model)
  - Backtest data placeholder ("Bexar County 2024 off-market hit rate: [pending Day 8]")
  - Loom demo video embed (recorded Day 3-4)
- [ ] Section 6 — About:
  - Photo of you (professional, real)
  - 2 paragraphs: who you are, why multifamily, why now (CMBS maturity wall context)
- [ ] Section 7 — CTA repeat: same form + Cal.com link
- [ ] **Performance:** Lighthouse score > 90 mobile, load under 3 seconds
- [ ] **Mobile-first:** test on iPhone viewport before deploying
- [ ] **One primary CTA:** "Get free OM analysis" everywhere; "Book a call" is secondary throughout

### Afternoon Block 3 — Wiring + Webhooks (~2 hours)

- [ ] Form submission → Supabase `contacts` table + Slack `#inbound` alert + Resend confirmation email + HubSpot contact create (single Vercel API route, ~100 lines)
- [ ] Cal.com booking webhook → Slack `#scheduling` + HubSpot stage to "Discovery Booked"
- [ ] Stripe webhook → Slack `#revenue` + `#wins` + HubSpot stage update to "Deposit Paid"
- [ ] RB2B webhook → Slack `#inbound` with identified visitor LinkedIn URL
- [ ] Install RB2B pixel snippet in landing page `<head>`
- [ ] Test all webhooks by triggering each manually

### Evening Block — Resend templates + Apollo + Cold message drafts (~3 hours)

- [ ] Draft 4 Resend email templates (these are for INBOUND only — opt-ins, clients, never cold):
  - **opt-in-confirmation:** "Thanks — building your analysis now. Back within 24 hours."
  - **drip-day-1:** sent 24 hours after opt-in if they didn't forward an OM yet. "Quick reminder: forward me any OM and I'll send analysis back same day."
  - **drip-day-4:** "Here's the methodology one-pager [link]. If anything in your current pipeline you want a second opinion on..."
  - **drip-day-8:** "Want to do a 20-min walkthrough? [Cal.com link]"
- [ ] Open Apollo, refine list to San Antonio + Austin multifamily syndicators. Verify the 5 Tier-1 names you'll send to tomorrow:
  - Ted Kerr, Crossbeam Capital, Managing Partner
  - Dustin Lapacka, CommonSense Ventures, Managing Partner
  - Richard Lowe, Pilot-Legacy Private Equity, Managing Partner
  - Philip Massari, Monte Vista Partners, Managing Partner
  - Martin Rico, Rosehaven Homes, Founder & CEO
- [ ] Quick website check on each — confirm they're actually multifamily syndicators (kill any imposters, replace from Austin list if needed)
- [ ] Unlock all 5 emails in Apollo. Verify each at Hunter.io
- [ ] Update LinkedIn profile: new headline ("Building AI-powered acquisition decision support for multifamily syndicators"), professional photo, banner image
- [ ] Write 5 personalized cold messages for Day 2 morning send. Each: 3-4 sentences, validation-era framing ("free analysis in exchange for 5-min feedback while I refine the tool"), specific reference to their firm, link to landing page, NO calendar link in first touch
- [ ] Draft LinkedIn Post #1, schedule for Day 2 morning publish

### End of Day 1 — Hard checkpoint

- [ ] Both domains registered, DNS configured, SPF + DKIM + DMARC live, MXToolbox passing
- [ ] Cold email warmup running on secondary outbound domain (5/day, ramping)
- [ ] Landing page live, all webhooks tested
- [ ] RB2B pixel firing
- [ ] All 5 cold messages drafted, ready to send tomorrow at 9 AM FROM YOUR EXISTING PERSONAL EMAIL (not the new domains — they're warming)
- [ ] Apollo list verified, emails unlocked
- [ ] LinkedIn profile updated
- [ ] LinkedIn Post #1 scheduled
- [ ] Resend templates drafted
- [ ] GitHub repo public

If any of these slipped: domain/DNS/warmup is the only Day 1 hard requirement. Everything else can slip 1-2 days. Warmup cannot — every day delayed pushes your warmed-domain go-live a day later.

---

## Day 2 — First cold sends (from existing email) + Sentinel work begins

### Morning Block 1 — Cold sends (~2 hours)

- [ ] **9 AM sharp:** Send 5 personalized cold messages from your existing personal Gmail or USF .edu, NOT from the new domains (they're warming).
  - Your existing email has years of reputation. Sending 5 cold/day from it is safe.
  - The new domains stay locked to warmup pools until Day 15+.
- [ ] Space sends 20-30 min apart to avoid simultaneous-send patterns
- [ ] Same 5 people: LinkedIn DM same day with abbreviated version (~50 words)
- [ ] Log all in HubSpot, move to "Contacted"
- [ ] LinkedIn Post #1 goes live (scheduled yesterday)
- [ ] Phone notifications ON for replies

### Morning Block 2 — Sentinel validation track begins (~4 hours)

- [ ] Set up validation tracking spreadsheet (Notion or Sheets): Run #, Property, Date, Pipeline completion Y/N, Skills failed, Error notes, Time to complete, Manual accuracy audit, Reviewer feedback
- [ ] Source 5 real broker OMs from public archives: BiggerPockets multifamily forum threads (search "offering memorandum"), LoopNet archived PDFs, your network, archive.org for old broker sites
- [ ] Run Sentinel on real OM #1 end-to-end
- [ ] Log everything that breaks
- [ ] Fix most critical break, re-run

### Afternoon — More Sentinel runs + inbound (~4 hours)

- [ ] Run real OMs #2 and #3
- [ ] Document errors per skill
- [ ] Identify top 3 error classes for tomorrow's fixes
- [ ] Phone on: respond to any inbound reply within 5 minutes
- [ ] If anyone forwards an OM today — drop everything, run it, send analysis back same day

### Evening — Next day prep (~2 hours)

- [ ] Verify next 5 Apollo prospects (expand to Austin if San Antonio runs short)
- [ ] Draft tomorrow's 5 cold messages
- [ ] Update HubSpot
- [ ] Check warmup tool: confirm secondary domain warmup is running, see day 1 stats

### End of Day 2 check

- [ ] 5 cold sends from existing email ✓
- [ ] 3 OMs through Sentinel ✓
- [ ] LinkedIn Post #1 live ✓
- [ ] Warmup ramping ✓
- [ ] Tomorrow's drafts ready ✓

---

## Day 3 — Volume up + Loom recording

### Morning (~3 hours)

- [ ] **9 AM:** 5 more cold sends from existing email (total 10)
- [ ] LinkedIn DM follow-up to Day 1 prospects who haven't replied (4-day window per cadence rules — but you sent Day 1, so wait until Day 5)
- [ ] Check RB2B for landing page visitors → any identified syndicators get LinkedIn DM same day
- [ ] Inbound monitoring

### Midday — Sentinel Track A (~5 hours)

- [ ] Run real OMs #4 and #5
- [ ] Now 5 OMs logged. Begin Gate 2 (Accuracy) audit:
  - For each output, pick 10 key facts (owner LLC, hold period, loan info, comps, permits)
  - Manually verify each against ground truth
  - Mark correct/incorrect
- [ ] Compute initial error rate per skill
- [ ] Top 2 highest-error skills: fix them (likely BCAD Stagehand owner_lookup and portfolio_crawler — county sites are messy)

### Afternoon Block — Content asset creation (~2 hours)

- [ ] Record the master Loom: 5-minute walkthrough of Sentinel running on a real OM end-to-end
- [ ] This becomes the sales asset embedded on the landing page AND shared in cold messages from this point forward
- [ ] Edit out dead time, add captions, export

### Evening (~2 hours)

- [ ] Embed Loom on landing page in "Proof" section
- [ ] Draft LinkedIn Post #2 ("Why loan maturity beats hold period for off-market multifamily"), schedule for Day 4
- [ ] Source 5 more real OMs for tomorrow

### End of Day 3 check

- [ ] 10 cold sends total ✓
- [ ] 5 OMs through Sentinel ✓
- [ ] Loom recorded and embedded ✓
- [ ] Gate 2 audit started ✓
- [ ] First inbound reply hopefully ✓

---

## Day 4 — 15 sends + blog post 1

### Morning (~3 hours)

- [ ] **9 AM:** 5 more sends (total 15)
- [ ] LinkedIn Post #2 goes live
- [ ] Inbound replies within 5 minutes
- [ ] Day 1 prospect LinkedIn follow-ups (now 4 days out)

### Midday — Sentinel Track A (~5 hours)

- [ ] Run OMs #6, #7, #8 (8 successful runs targeting Gate 1's 10)
- [ ] Continue Gate 2 audit on each new run
- [ ] Sharpen Nemotron synthesis prompt based on accuracy findings — add "if you don't have data on X, write 'data unavailable for X'" to combat hallucination

### Afternoon — Blog post #1 (~2 hours)

- [ ] Write 1500-2000 word blog post: "The hidden bottleneck in multifamily acquisitions isn't deal flow — it's analyst hours"
- [ ] Include: the problem framing, the 6 signals Sentinel scores, methodology link to GitHub, embedded Loom
- [ ] Schedule to publish Day 6 (weekend traffic isn't great; publish Monday for max engagement)

### Evening (~2 hours)

- [ ] Verify next 5 prospects, draft tomorrow's sends
- [ ] Check warmup stats — secondary domain should be sending ~15 emails/day to warmup pool now
- [ ] Update HubSpot
- [ ] **Sleep 7+ hours minimum.** Day 5 is the 20-send pivot decision.

### End of Day 4 check

- [ ] 15 cold sends total ✓
- [ ] 8 OMs through Sentinel ✓
- [ ] Blog post drafted ✓
- [ ] LinkedIn Post #2 live ✓

---

## Day 5 (Friday) — 20-send pivot decision + Gate 1 close

### Morning (~3 hours)

- [ ] **9 AM:** 5 more cold sends (total 20 — hit the validation gate)
- [ ] LinkedIn Post #3 goes live (the methodology/proof piece)
- [ ] Inbound monitoring

### MIDDAY DECISION POINT (~1 hour)

Tally the 20-send data and make the pivot call.

- [ ] Replies received?
- [ ] OMs forwarded?
- [ ] Discovery calls booked?

Decision matrix:
- **1+ reply OR 1+ discovery call OR 1+ OM forwarded:** keep current message variant, continue at 5/day next week
- **0 of everything at 20 sends:** PIVOT one variable. Most likely change in priority order:
  1. Subject line (try "free OM analysis for [firm]?" vs current "cutting OM triage...")
  2. Lead paragraph (try opening with their specific firm context vs the analyst-hours hook)
  3. ICP (try Director of Acquisitions instead of Managing Partner)
  4. Geography (Austin/Dallas instead of San Antonio only)

Document the pivot decision in writing. New variant runs starting Day 8.

### Afternoon — Sentinel Gate 1 close (~5 hours)

- [ ] Run OMs #9 and #10 to push toward Gate 1's "10 consecutive successful end-to-end runs"
- [ ] If any of #9-10 fails, fix and re-run
- [ ] **By EOD: target GATE 1 PASSED — document this milestone in master plan validation tracker**
- [ ] Continue Gate 2 audit across all 10 runs

### Evening (~3 hours)

- [ ] LinkedIn post: share the Loom standalone with caption: "90 seconds. Real broker OM. Full public-records due diligence. Comments open if you want yours analyzed."
- [ ] Update HubSpot
- [ ] Plan weekend work

### End of Day 5 / Week 1 check

- [ ] 20 cold sends total ✓
- [ ] Pivot decision made (if needed) ✓
- [ ] 10 OMs through Sentinel ✓
- [ ] GATE 1 PASSED ✓
- [ ] 3 LinkedIn posts + 1 standalone Loom + Day 6 blog post scheduled ✓
- [ ] Ideally: 1+ reply, 1+ OM forwarded, 1+ discovery call booked
- [ ] Warmup tool: domain is ~25 emails/day now, halfway through 14-day ramp

---

## Weekend (Day 6-7) — Heavy push, NOT rest

### Saturday (~12 hours)

- [ ] Morning: blog post #1 publishes on landing page. Promote on LinkedIn, X, Reddit (r/realestateinvesting, r/CommercialRealEstate — check each subreddit's self-promo rules first; some prohibit it)
- [ ] Sentinel Gate 2 — finalize accuracy audit on all 10 runs
  - Compute overall error rate (target <10%)
  - Compute critical-signal error rate (loan maturity, owner, hold period — target <5%)
  - If thresholds passed: **GATE 2 PASSED**, document
  - If higher: identify worst-performing skill, dedicate today + Sunday to fixing
- [ ] Polish the PDF deliverable template to look like a real consulting product (Typst, LaTeX, or HTML→PDF with serious layout)
- [ ] Recruit Gate 3 reviewers:
  - Post on BiggerPockets multifamily forum: free OM analysis in exchange for 5-min feedback
  - Message 5 friends-of-friends in real estate
  - Post in r/CommercialRealEstate offering free analyses
  - Target: 2 outside reviewers committed by Sunday EOD
- [ ] Re-engage any prospect who replied in Week 1 but didn't book: forward a market insight, share the blog post

### Sunday (~8 hours)

- [ ] Pre-build Monday's 5 cold message drafts
- [ ] Verify next 10 Apollo prospects
- [ ] Sentinel: address remaining Gate 2 issues
- [ ] Send Gate 3 reviewer onboarding (their first OM + output to score)
- [ ] Polish landing page based on Week 1 traffic data (Plausible/GA)
- [ ] 3-hour break in the evening. Real food. 7+ hours sleep.

---

## Day 8 (Monday) — Week 2 + Gate 3 launch

### Morning (~3 hours)

- [ ] **9 AM:** 5 cold sends (total 25)
- [ ] LinkedIn Post #4 (drawing on real Week 1 lessons or specific Sentinel finding, anonymized)
- [ ] Inbound monitoring
- [ ] **Warmup check:** secondary domain is ~Day 8 of warmup, sending 25-30/day to warmup pool. Still 7+ days from being ready for real cold sends.

### Midday — Track A: Gate 3 (~4 hours)

- [ ] Send 3 outputs to each of the 2 outside reviewers (6 outputs being rated)
- [ ] Formal Gate 3 tracking spreadsheet active
- [ ] Continue Sentinel hardening

### Afternoon — Discovery calls (~3 hours)

- [ ] Take any scheduled calls
- [ ] Post-call: send Sentinel analysis on a property they mentioned. Propose follow-up call.
- [ ] If a call goes well: pitch the 30-day pilot offer

### Evening — Content engine cycle (~3 hours)

- [ ] Record 10-minute voice memo: something you learned about the niche this week
- [ ] Run amplification through Claude: LinkedIn long-form + X thread + newsletter section
- [ ] Schedule LinkedIn Post #5 from amplification for Wednesday
- [ ] Update HubSpot

### End of Day 8 check

- [ ] 25 cold sends total ✓
- [ ] Gate 3 reviews in flight ✓
- [ ] Voice memo amplification cycle started ✓

---

## Day 9 (Tuesday) — Pipeline push

### Morning (~3 hours)

- [ ] 9 AM: 5 more sends (total 30)
- [ ] Aggressively work pipeline. Every reply gets a follow-up today.
- [ ] Inbound monitoring

### Midday — Track A (~3 hours)

- [ ] Gate 3 feedback processing
- [ ] Adjust outputs based on reviewer feedback
- [ ] If any reviewer rates below 5/10: deep dig into why

### Afternoon — Close pushes (~5 hours)

- [ ] Discovery calls
- [ ] Post-call: pitch the 30-day pilot: "$2K for 30 days, OM analyses included, San Antonio sample list. Full retainer kicks in day 30 if you renew. Want to do it?"
- [ ] One-page proposal within 2 hours of any call that wants to think it over

### Evening (~2 hours)

- [ ] Inbound handling
- [ ] Tomorrow's drafts
- [ ] LinkedIn Post #5 scheduled

---

## Day 10 (Wednesday) — Gate 3 close + close push

### Morning (~3 hours)

- [ ] 9 AM: 5 more sends (total 35)
- [ ] LinkedIn Post #5 goes live
- [ ] Inbound monitoring

### Midday — Track A close (~3 hours)

- [ ] Finalize Gate 3: average reviewer ratings
- [ ] If passed (≥7/10 average, no <5): **SENTINEL OFFICIALLY VALIDATED**
- [ ] Update landing page hero copy, LinkedIn, GitHub README to reflect "validated tool" framing
- [ ] If not passed: identify specific criticism, fix before continuing to charge anyone

### Afternoon — Close push (~6 hours)

- [ ] Every active prospect: contract sent, payment link sent, OR explicit "not now" with reason logged
- [ ] Discovery calls
- [ ] Proposal follow-ups: "What would help you say yes this week?"

### Evening (~2 hours)

- [ ] Send a market insight email to all pipeline prospects (cold and warm) — pure value, no ask. Re-warms them.

---

## Day 11 (Thursday) — Contract push + production-readiness

### Morning (~3 hours)

- [ ] 9 AM: 5 more sends (total 40)
- [ ] LinkedIn Post #6
- [ ] Inbound monitoring

### Midday — Client onboarding build (~3 hours)

- [ ] Build the client onboarding mini-experience:
  - Welcome email template
  - Slack Connect channel template structure
  - OM forwarding flow
  - First weekly list deliverable template
  - "What happens in your first 7 days" doc for client
- [ ] Test full onboarding end-to-end as fake client

### Afternoon — Close push (~6 hours)

- [ ] Every proposal-stage prospect gets a CALL today. Email is dead at this stage.
- [ ] Pitch the founding client offer: "$5K setup + $4K/mo, 6-month term, BUT first 30 days free. Sign today, start tomorrow, decide on day 30 whether to fund."

---

## Day 12 (Friday) — Contract close attempts

### Morning (~3 hours)

- [ ] 9 AM: 5 more sends (total 45)
- [ ] LinkedIn Post #7
- [ ] Inbound monitoring

### Midday — Preview deliverable (~3 hours)

- [ ] If a contract is close to signing: build the FIRST WEEKLY DELIVERABLE for that prospect's submarket and thesis. Send as preview — "here's what week 1 looks like, even before you sign"
- [ ] If no prospect is close: harden Sentinel — add 3 more edge cases, write per-client config

### Afternoon — Final close push (~6 hours)

- [ ] Every proposal-stage prospect: phone call
- [ ] Push for signature today
- [ ] By EOD: at least 1 signed contract OR explicit "next week" date from a serious prospect

---

## Weekend (Day 13-14) — Final push + warmed domain prep

### Saturday (~12 hours)

- [ ] If contract signed Friday: execute kickoff (Slack Connect channel, welcome email, first 30 days plan)
- [ ] If not signed: re-engage every "not yet" prospect. Find the closest. Push hard.
- [ ] 5 more cold sends from existing email (total 50)
- [ ] Personal email to 5 warm-network contacts: direct intros to multifamily syndicators
- [ ] Sentinel: any final polish based on real-world feedback
- [ ] **Warmup check: secondary domain at Day 13 of warmup. Day 15 = ready for production cold sending.**

### Sunday (~8 hours)

- [ ] Contract close attempt #2 if needed
- [ ] Final Sentinel polish
- [ ] **CRITICAL Sunday task:** prepare the transition from existing email → warmed secondary domain for Week 3+ cold outreach
  - Domain warmup hits Day 14 tomorrow
  - Verify the warmup tool shows healthy stats (good open rates from pool, no spam complaints)
  - Cap initial sends from warmed domain at 10-15/day for Week 3, ramp to 25-30/day by Week 4
  - Keep warmup running in background even after starting cold sends — never stop warmup

---

## End of Day 14 — Outcomes

**Money-in best case:** $5K deposit wired, kickoff Monday. Goal exceeded.

**Contract-signed realistic case:** signed contract with 30-day free pilot, deposit due day 30. Goal achieved per floor.

**Honest middle case:** 2-3 prospects in proposal, 1 leaning yes, close week 3. Extend sprint.

**Failure mode:** 50 sends, 0 replies after pivoting. Stop. Reassess. The message OR targeting is fundamentally wrong.

---

## What's tracked daily (the discipline)

Every day before bed, update:

1. **Sends sent today / total cumulative** (from existing email Week 1-2, from warmed domain Week 3+)
2. **Replies received today / cumulative**
3. **OMs forwarded today / cumulative**
4. **Discovery calls today / scheduled / completed**
5. **Sentinel runs today / cumulative**
6. **Validation gate status** (Gate 1/2/3 PASS/PENDING/FAIL)
7. **Landing page traffic today** (Plausible)
8. **RB2B identifications today**
9. **LinkedIn post engagement** (impressions, profile views, replies — Mon-Fri only)
10. **Warmup domain status** (day N of warmup, daily send count, pool open rate)
11. **Pipeline status per active prospect** (HubSpot)
12. **Single biggest blocker right now** — the most important field. Same blocker 3 days in a row = tomorrow's only priority.

---

## The infrastructure cheat sheet (updated for 2026)

If you ever forget what's where:

- **Primary domain:** `<yourbrand>.com` — landing page, client communication, identity
- **Secondary outbound domain:** `try<yourbrand>.com` — cold email ONLY, after Day 15 warmup completes
- **DNS:** Cloudflare (both domains)
- **Email infrastructure (primary):** Google Workspace, `gurnoor@<yourbrand>.com` — for client comms + landing-page-attached email + Resend transactional
- **Email infrastructure (outbound):** Google Workspace, `gurnoor@try<yourbrand>.com` — cold outreach only, post-warmup
- **Email warmup tool:** Instantly or Smartlead, running continuously
- **Email authentication:** SPF (`v=spf1 include:_spf.google.com ~all`), DKIM (2048-bit via Google admin), DMARC (start `p=none` 30 days, then `p=quarantine`)
- **Cold outreach Weeks 1-2:** From your existing personal Gmail/USF email (existing reputation), 5/day max
- **Cold outreach Week 3+:** From warmed secondary domain, ramp 10→25-30/day
- **Landing page:** Next.js + Vercel, deployed on primary domain
- **Database:** Supabase (contacts, sends, artifacts, clients, om_analyses)
- **Transactional + drip:** Resend (4 templates wired, INBOUND ONLY)
- **Calendar:** Cal.com
- **Payments:** Stripe (3 links)
- **CRM:** HubSpot Free (10-stage pipeline)
- **Visitor ID:** RB2B pixel on landing page (8-15% person-level match for US traffic)
- **Team OS:** Slack (12 channels per master plan)
- **Code repos:** GitHub (Sentinel open-source signal model)
- **LLM for Sentinel:** Nemotron via NVIDIA NIM
- **LLM for content amplification:** Claude Sonnet 4.6
- **Monitoring:** Google Postmaster Tools for primary domain reputation, MXToolbox for ongoing DNS health checks

---

## The non-negotiable rules

1. **Never cold-email from primary domain.** Burns it in 30 days.
2. **Never skip domain warmup.** 14-21 days minimum before first cold send from a new domain.
3. **Never exceed 30 emails/day per mailbox.** Google throttles bulk senders above this.
4. **Never use `-all` SPF on day one.** Start with `~all` (soft fail) until you've verified all sending sources.
5. **Never set DMARC to `p=reject` on day one.** Start at `p=none` for 30 days, then `p=quarantine`.
6. **Never break the SLA.** 48hr Mon-Thu, 72hr Fri-Sun for OM analyses.
7. **Never let a track swallow the others.** A, B, and C all happen every day from Day 2 onward.
8. **Never skip the warmup check.** Days 8, 11, 14: verify warmup is healthy. A bad warmup pool burns your domain worse than no warmup.

---

## The honest final word

This plan integrates 2026 best practices that didn't exist or weren't enforced when older cold-email playbooks were written. The big shift: cold email in 2026 is infrastructure-first. You cannot copy-paste a 2022 playbook and expect it to work — Google, Microsoft, and Yahoo's enforcement made domain authentication and warmup non-negotiable.

The reason this version sends from your existing personal email Weeks 1-2 isn't laziness. It's discipline. Your existing email has years of reputation. The new domains need 14-21 days of warmup to earn similar trust. Trying to shortcut warmup is the #1 reason cold email campaigns fail in 2026.

By Day 15-21, the warmed domain is ready and you transition to it. By then, you also have validation data on Sentinel and ideally a signed contract.

Day 1 is infrastructure. Day 2 at 9 AM: 5 cold messages from your existing email. Stop planning. Start operating.
