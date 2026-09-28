# Audience experiments and unit economics

## Pilot design

After visual approval, release 12–18 distinctly authored episodes over about four weeks at a sustainable cadence. Keep the cast and overall look consistent. Balance cooperation, competition and mystery families; avoid comparing an entirely new style, language and plot simultaneously. Predeclare the main variable for each comparison. This is an exploratory pilot with substantial platform noise, not a guaranteed sufficient sample.

YouTube Shorts is the first measurement surface. Other platform exports may follow, but their metrics and revenue remain separate. Do not treat cross-platform views as unique viewers or sum incompatible definitions into one engagement rate.

## Experiment register

Each experiment stores ID, hypothesis, audience, creative change, control/comparison set, planned episode count, publish window, primary metric, guardrails, minimum evaluable exposure selected before results, and decision date. Default primary pilot metric: seven-day engaged views per episode; compare completion/retention and shares alongside it. This choice is a project hypothesis and may be revised prospectively.

If exposure is insufficient, label the result inconclusive. Avoid declaring a winner from a handful of views. Compare medians and per-video distributions at the same age; list outliers separately. Observational comparisons across different episodes cannot isolate every cause.

## Data and metric rules

Persist raw imports and version the normalisation mapping. Every metric includes its platform definition, timeframe and denominator. Keep missing, unavailable and zero distinct. Deduplicate repeated snapshots and avoid summing cumulative totals across collection dates.

Record at approximately 24 hours and seven days: available view counts, engaged views, watch-time/retention measures, shares, comments, subscriber changes and actual revenue. Save geography and returning-viewer information only at the granularity the source supplies; never invent video-level values from channel-level metrics.

The YouTube Analytics API documents metrics such as engaged views, average view duration, average percentage viewed and audience-retention measures, but supported report/dimension combinations must be checked during implementation. Studio-only or unavailable metrics use manual import or null. [YouTube Analytics metric definitions](https://developers.google.com/youtube/analytics/metrics)

For Shorts revenue, YouTube uses eligible engaged views. Public views are therefore not interchangeable with the revenue denominator. [YouTube Shorts monetisation](https://support.google.com/youtube/answer/12504220?hl=en)

Derived project ratios must say exactly what they divide. For example, `shares / engaged_views × 1,000` is a project-defined ratio, not necessarily a platform's native share rate. Do not calculate it if its denominator is missing or zero. Average percentage viewed above 100% can reflect repeat playback; it is not the percentage of people who deliberately rewatched. Do not infer loyalty from completion alone.

## Weekly decisions

For each format, show accepted and rejected output counts, operator minutes, production cost, exposure, available audience outcomes and examples of qualitative viewer responses. Comments are selected observations, not representative audience research by default.

- Continue a format when several episodes show promising audience response at an acceptable production burden.
- Improve staging or pacing when the same timecoded issue appears across independent reviews or retention curves.
- Retire an expensive shot type if rejection and repair costs dominate its contribution.
- Test language/geography when there is enough baseline performance to interpret the change. Use language-specific packaging and culturally meaningful writing; do not simply swap a flag.
- Stop scaling when quality declines or outputs become repetitive. Revise the format before increasing volume.

These are decision principles. Numerical growth or profitability thresholds must be chosen by the owner using observed baseline and available time, not invented as universal viral-video benchmarks.

## Revenue and growth

Before monetisation, report confirmed revenue as zero; measure leading indicators without calling them earnings. Once monetised, use the channel's actual net revenue and denominator. Analyse country mix from real reports; do not assume Indian viewers are less valuable in every business model or global distribution automatically yields US/UK traffic.

Longer episodes, sponsorships, licensing and merchandise are later options if a recognisable audience develops. Do not include hypothetical sponsorship income in production ROI. Reconfirm platform eligibility and policies at launch instead of hardcoding thresholds into the product. [YouTube monetisation policies](https://support.google.com/youtube/answer/1311392?hl=en)

## Guard against misleading optimisation

No fake views, fabricated comments, automated engagement or misleading promise of a payoff that never arrives. Useful optimisation improves the story people chose to watch. Do not train a retention model on tiny pilot data; collect a reliable labelled history first. Automated editorial scores remain diagnostic features, never ground truth for audience response.
