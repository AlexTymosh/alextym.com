# People Voice interview flow

1. Sign in with the Workforce demo password and open **People Voice →
   Survey builder**. Choose **Career Development and Progression**. Use
   **Current workforce**, **All service areas**, the default dates and the
   free-text question from the bank. Keep **Anonymity minimum** at 5 and select
   **Create campaign**.
2. In **Campaigns & responses**, set **Response count** to 15 and **Seed** to
   32. Select **Generate significant concern**. Confirm that **Analysable
   comments** is at least 5. A rating can appear in Survey analytics. The AI
   analysis uses the written comments.
3. Open **Analyst review**, select the campaign and choose **Analyse with AI**.
   Allow up to a minute for **External AI analysis** to show **Ready**. A timed
   out run shows a separate message and can be retried. **Use demonstration
   analysis** runs the known synthetic classifications for an offline fallback.
4. Open **Validated evidence** on a finding that meets the anonymity rule.
   Save a review decision with a rationale, then publish it separately.
   Amendments, evidence splits and merges preserve review history. Potentially
   serious signals require priority human review.
5. Create a management action against the published finding. Enter the team,
   baseline, target, expected benefit and due date. Start the work and record
   closure evidence when it is complete. The app sends no notifications.

Use **Survey analytics** to compare weighted and unweighted theme estimates. A
blank estimate means a small sample or complement was suppressed, or the known
population totals could not support weighting. The prepared **Rota Changes and
Workforce Pressure** report is under **Prepared example**.

## Methods and scope

- Population and invitation counts are frozen for each single-dimension
  partition at generation. Workforce membership comes from effective contracts
  and assignments on the campaign cutoff. For exit surveys, the cutoff is the
  day before leaving. Qualification groups are explicitly synthetic proxies, not
  actual qualification records or evidence of respondent credibility.
- Representation weights divide eligible population share by respondent share,
  clipped to 0.5–2.0 by default. Effective sample size is
  `(sum of weights)² / sum of squared weights` over analysable responses. The
  application does not adjust observations for answer validity or non-response
  bias. A comparison must have the same series, audience and service-area scope.
- Small denominators, nonzero cells below the threshold and small complementary
  cells are withheld before the API response. If one cell would expose a
  suppressed value, the whole breakdown is withheld. Only one dimension is
  accepted at a time. Source theme mentions and distinct responding comments
  have different counts. Associations with independently recorded learning and
  PDR measures do not establish causation.
- The priority formula and component weights are shown with each available
  signal. They order review work only. Serious signals can be flagged even
  when their numeric estimate and individual evidence are withheld.
- The external provider receives at most 60 selected synthetic comments and a
  question from the bank, with identifier redaction applied first. For a custom
  question the provider receives a predefined question from the bank. It does not
  receive employee data, segment attributes, member identities or credentials.
  The [OpenAI Structured Outputs contract](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)
  provides schema validation. The model selects IDs for supplied excerpts.
  The backend resolves the IDs to literal excerpts, counts distinct responses,
  and verifies the resulting evidence. Provider failure or invalid evidence
  creates a failed run with no publishable findings. Demonstration analysis
  uses known synthetic source labels and follows the same review gates.
- People Voice shares the backend's `OPENAI_API_KEY`, `OPENAI_MODEL` and
  `OPENAI_REASONING_EFFORT` with the website chat. It sends text and receives
  structured evidence from the Responses API. The classifier has its own output
  budget and a 45-second provider timeout. The Workforce proxy allows 55 seconds
  for analysis and 25 seconds for other operations.
- Analysts act through a shared password-protected demo session. Review events
  identify the demo account and correlation ID, not an individual. A personal
  Firebase identity and tester grants are deferred. Never use actual workforce
  or patient data in this demonstration.
