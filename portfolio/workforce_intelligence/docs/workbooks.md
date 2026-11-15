# Excel import and export

In Workforce Management, open **Import / Export** and download the current
template. Use fictional aliases, codes and dates only. Keep the
`Workbook information` sheet and the header row of each sheet you use. Empty
optional sheets can be removed. Enter values only, with ISO dates or Excel dates
without a time. Use the `action` column to distinguish changes on the same
sheet. The template lists the accepted actions.

| Sheet | Matching key and permitted work |
| --- | --- |
| ReferenceData | Reference type and code; create or update active values. Establishment lines and campaigns use their own ID. Put new references before lines that use them. |
| Employees | Employee ID; create a profile with initial contract/assignment or edit the synthetic alias or optional categorical profile attributes. |
| Contracts | Employee ID and effective date; add a dated interval or correct the interval at the same boundary, with audit. |
| Assignments | Employee ID and effective date; transfer or record progression. |
| Vacancies | Vacancy ID; request, approve, publish, or close/cancel in chronological row order. |
| Applications | Application ID; record receipt, ordered stages and interview outcome. |
| Offers | Offer ID; create the conditional offer and record its decision. |
| PreEmploymentChecks | Offer ID and check date; record ordered pending, passed or failed checks. |
| NewStarters | Application ID for planned confirmation; offer ID for actual start; employee ID and date for probation. |
| Learning, PDR | Event ID; create or update the event for the same employee. |
| Leavers | Employee ID; end employment on the first inactive day. |
| SurveyResponses | New survey ID and response IDs. Choose an allowlisted synthetic comment code: `none`, `rota_pressure`, `development`, `communication` or `positive`. Already analysed evidence cannot be edited. |

Sheets apply in the order shown, and rows within a sheet apply top to bottom.
For example, an application must precede its offer, checks and starter.
The date-only closure of a vacancy is effective at the end of its recorded
closing day. Thus a closed vacancy may still receive historical recruitment
rows dated on or before that closing day, even though the Vacancies sheet
precedes Applications in the import order. Rows dated after closure are rejected. Use the
employee ID displayed in **New starters** if you want to follow up with a
separate employment import. Matching values are reported as unchanged; duplicate
business keys within a workbook must be resolved before confirmation.

**Validate workbook** shows the planned inserts, updates and unchanged rows,
each rejected row's sheet and number, and projected effects on the dashboard.
The server checks commands on an isolated copy of the dataset. There is no write
to operational records before **Confirm import**. An invalid row blocks the batch.
Download the validation report to fix the original worksheet and revalidate it.

Confirmations apply only to the current dataset ID, generation and preview
revision. They expire after 15 minutes, and any intervening source edit or reset
requires a new preview. In a single SQLite transaction, confirmation applies
validated rows, writes row and batch audit events, and commits the receipt. Gold
reads the resulting revision without a separate refresh job. A retry by the
same Member returns the same receipt. The owner of the upload can download the
issue list. An incomplete or failed transaction never applies part of a book.

Downloads cover executive metrics and the application funnel, the metric
catalogue, quality diagnostics, and published survey findings with permitted
evidence. A vacancy filter scopes the funnel; the executive metrics still use
the selected reporting period across the dataset. The version, cutoff and
synthetic disclosure are in the workbook. No formula cells are written.

Both hosts require a Member grant. Writes from the browser also require a
same-origin request. Limits are 1 MiB uploaded, 500 data rows, 32 columns,
12 MiB uncompressed archive size and 128 staged or committed batches per
generation. External links, encryption, embedded files and macro workbooks are
unsupported. Member limits are 6 validation calls, 10 confirmations and 20
downloads per 60 seconds, with separate project-wide limits. The uploaded ZIP
stays in memory; staging keeps validated commands, row diagnostics and the
batch receipt inside Workforce SQLite. Reset removes staged and committed batch
data along with the rest of the shared demo records.
