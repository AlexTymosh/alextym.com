# PR5 / commit 15: data quality explanation and source register

The existing `GET /api/workforce/data-quality` is the sole source of the four
currently implemented record-exclusion and unassigned-contract counts. The UI
adds rule explanations and likely metric impact without recalculating counts,
introducing a new API, or claiming that every specification quality dimension is
covered. A `passed` status means **these implemented checks** found no issues,
not that completeness, validity, uniqueness, timeliness or equality are fully
certified. Counts per rule can overlap and are not summed.

The Data Architecture page now contains a version-controlled Sources and
Assumptions register. Project-local synthetic data, modelling assumptions and
public contextual sources are distinguished. The public SCAS links come from
Technical Specification v1.2 Appendix A: their reachability, publication dates
and current content **have not been independently verified for this release**.
No numerical results from those documents are presented as synthetic outcomes.
The register is presentation metadata, not an ingestion or data-processing path.

## Still to implement before full PR5 acceptance

- A richer server-side quality-rule catalogue and impact gating for materially
  invalid metrics, with severity, owner, date, quality dimension and issue trend.
- Reconciliation/validity/timeliness tests for all specified analytical sources.
- Independently reviewed public reference dates and source links.
- Privacy testing for cross-revision differencing and sensitive survey threshold
  10 before any further demographic or survey breakdowns are released.

The new browser checks verify the rule-detail table and register appear inside
the protected Data Architecture mode. They do not constitute a privacy audit.
