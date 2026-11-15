# PR5 / commit 15, first slice: Inclusive Recruitment disclosure boundary

`GET /api/workforce/analytics/inclusive-recruitment` is a protected Workforce-member
endpoint, not a public or per-candidate API. It shows only synthetic aggregated
application-grain data. Every API response is computed against the committed dataset
revision and the dataset's fixed `as_of_date`.

## Scope and definitions

- The cohort is **all observed, valid Silver applications** received on or before
  the dataset cutoff, not distinct people, recruitment requests or stage events.
- Permitted separate dimensions: age band, broad ethnicity group and disability
  declaration. No cross-tabulation, vacancy, organisation or time slicing.
- Missing, unknown and invalid source codes map to `not-stated`, not to a guessed
  protected attribute. Values are fixed categories, not user-supplied labels.
- Stage counts are unique applications with a recorded event by cutoff. Repeated
  stage events and multiple offers cannot increase the application count twice.
- Shortlisting, interview and appointment rates use all applications in their
  group's cohort; offer acceptance uses offers made as its denominator. All
  rates are observed-by-cutoff, **not** final cohort outcomes.
- No WRES benchmark or real NHS demographic information is mixed with synthetic
  results. These outputs are descriptive, not evidence of discrimination or cause.

## Conservative suppression

The minimum permitted displayed cell count is **5**. A demographic dimension
is suppressed *in full* when any nonzero category cell or any difference between
reported stage counts is in `1..4`. This suppresses visible complements too:
if 20 applicants include 18 shortlisted, the two not shortlisted cannot be
reconstructed by subtracting released counts. For a suppressed dimension, **all**
counts and calculated rates are `null`, with `status: "suppressed"` and an
explanation. An empty cohort produces `status: "unavailable"` instead of `0%`.

No query string is accepted on this endpoint, even when bypassing the frontend
BFF. This prevents users from reconstructing small groups by intersecting
filters. The BFF additionally rejects unexpected query parameters. The endpoint
never returns application IDs, employee IDs or individual demographic records.

This is intentionally more conservative than cell-only suppression and may hide
whole dimensions on the small interview fixture. It is a working confidentiality
gate, **not** proof against every possible multi-revision inference attack in a
shared mutable demo. Before production use, complete independent privacy review,
revision-differencing tests and access audit.

## PR5 / commit 15: disclosure-controlled dashboard

The Workforce Intelligence page now renders the three **server-released** demographic
aggregations. Entirely suppressed dimensions show an explanation rather than a
partial table; a zero-denominator rate is displayed as `Not available`.
All published groups, counts and percentages come from the protected API, not
from client-side filtering or recomputation. The visible page states explicitly
that this is the **fixed full observed cohort**: changing the executive date range
or the candidate-funnel vacancy does **not** filter inclusive recruitment.
The frontend matches the inclusive dataset generation/revision with the other
analytical responses. The BFF rejects attempts to add query parameters.

## Not yet implemented

Further stage conversion and recruitment-likelihood ratios, population
eligibility/source register, quality impact badges and WRES contextual labels
remain subsequent PR5 work. Survey breakdowns require the separate threshold
**10** and must not reuse this threshold blindly. Multi-revision disclosure
risk is not solved by the UI and requires independent verification.
