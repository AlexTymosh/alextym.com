# People Voice interview flow

1. Sign in with the Workforce demo password and open **People Voice**. The
   original **Rota Changes and Workforce Pressure** report is available immediately.
2. Open **Survey builder**. Choose **Career Development and Progression** or
   **Wellbeing and Communication** for the two on-demand examples. Set the
   audience and dates, and create a campaign. Questions come from the bank or a
   custom prompt; the builder supports a 5- or 7-point rating scale.
3. Generate balanced, emerging, significant or exploratory responses. The
   campaign shows the seed, invitations, responses and analysable comments.
   For the short interview fixture, 15 responses with seed 32 in the
   significant scenario are useful. The full dataset supports larger samples.
4. Compare weighted and unweighted theme estimates in **Survey analytics**.
   Choose one segment or an approved weighting basis. A blank estimate means
   the sample or its complement is too small, or known population totals do not
   support weighting.
5. Choose **Use demonstration analysis** to complete the scenario without an
   external service, or **Analyse with AI** to use the configured OpenAI server
   integration. Check a draft's evidence, save a decision with a rationale, and
   then publish it explicitly. Amendments, evidence splits and merges preserve
   review history. Potentially serious signals require priority human review.
6. Create a management action against the published finding. Enter the team,
   baseline, target, expected benefit and due date. Start the work and record
   closure evidence when it is complete. The app sends no notifications.

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
  predefined question, with identifier redaction applied first. It does not
  receive employee data, segment attributes, member identities or credentials.
  The [OpenAI Structured Outputs contract](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)
  provides schema validation. The backend independently verifies each evidence
  ID, exact excerpt and distinct count. Provider failure or invalid evidence
  creates a failed run with no publishable findings. Demonstration analysis
  uses known synthetic source labels and follows the same review gates.
- Analysts act through a shared password-protected demo session. Review events
  identify the demo account and correlation ID, not an individual. A personal
  Firebase identity and tester grants are deferred. Never use actual workforce
  or patient data in this demonstration.
