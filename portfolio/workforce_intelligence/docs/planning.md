# Workforce forecasting and scenarios

Use **Workforce Intelligence → Forecasting** to inspect monthly actuals and
select **Enable forecast**. The controlled interview fixture covers four months.
**Load full dataset** replaces it with 36 months of synthetic history after
confirmation. The dashboard's as-of date caps all forecast inputs. Complete
history before that date is used even when the executive reporting window is
shorter. A partially observed current month is skipped for training and
projection. The first forecast is the next full calendar month.

| Measure | Observed monthly grain |
| --- | --- |
| Open vacancy WTE | Approved open WTE less recorded fills at month end |
| Workforce gap | Month-end budgeted minus substantive WTE |
| Recruitment starts | Dated conformed actual starts |
| Applications | Conformed applications received during the month |
| Median time to hire | Vacancy approval to offer acceptance, grouped by acceptance month |
| Early attrition | Early leavers among starters reaching 365 days of follow-up in the preceding 365 days, with at least five eligible starters |

At least 18 consecutive usable months are required for the comparison.
Trailing gaps yield an insufficient-history result. Genuine zeroes remain in
the series. Rolling one-month-ahead validation uses the most recent 6 to 12
eligible monthly origins and compares mean absolute error in the metric's
units. Seasonal naïve repeats the last 12 complete observations. Simple
exponential smoothing uses a fixed alpha of 0.35. The model with the smaller
unrounded validation error wins. Ties select seasonal naïve. The chosen method
is refit on all usable months. The horizon is 1 to 12 months. These are
synthetic point estimates. The short one-step validation supplies no
calibrated prediction interval or multi-step accuracy guarantee.

## What-if scenarios

**What-if scenarios** starts both paths at the observed open vacancy WTE,
substantive WTE and establishment on the chosen date. It compares edits with
the fixed reference inputs displayed in the form. Reference parameters are
illustrative assumptions. Opening WTE values are calculated from the dataset.

Each month adds approved positions. The model multiplies applicants per
position by the sequential conversion rates, capped at one fill per position.
The time assumptions determine when new cohorts start using 30-day planning
buckets. A separate total for planned starts uses existing vacancy capacity,
capped by available positions and WTE, then spread over the horizon. Internal
appointments fill a position without increasing substantive WTE. A monthly
retention factor derived from 12-month early attrition applies to prior
external starter WTE. Budget and the existing workforce are held constant.
Vacancy WTE and the signed workforce gap are separate outputs.

The model excludes cancellation, backfill, unplanned leavers and further
activity on the opening pipeline. Expected time to fill applies to successful
new positions conditional on the input times. Fractional expected starts express
the expected flow. These projections do not estimate the future performance of
SCAS or any real service.

Runs use the dataset UUID, generation, revision, model version and validated
inputs. Identical requests produce the same run ID. A concurrent source edit
returns 409 and a reset removes the stored runs. Results and scenarios belong to
the same disposable Workforce SQLite database as their inputs.
