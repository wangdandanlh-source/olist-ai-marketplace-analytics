# A/B design: Proactive Delay Communication

Status: DESIGN ONLY. No experiment was run and no results are claimed.

## Hypothesis and evidence

Clear delay notice, a reliable revised ETA and explicit next steps may reduce waiting-related customer contacts and low-score events. Historical evidence is associative: adjusted OR 2.31 and waiting-topic timing sensitivity. Historical 7.40% and 2.22% are late-delivery rates within written-review samples, NOT the experiment primary baseline.

## Eligibility / randomization

Pilot with index orders that are not delivered at the first check after original ETA, not already canceled, with an eligible contact channel. This deterministic rule does not assume an existing delay-prediction model. Operational event logging and consent settings must be ready before launch. Do not enroll only eventual responders or use future delivery outcomes to select customers.

Randomize customer 1:1 at first eligibility, using one first eligible index order for the primary endpoint. Persist assignment for subsequent orders to reduce contamination. Block by calendar week and pre-treatment shipping region if sufficient cells exist; record assignment before messaging. Check sample-ratio mismatch and tracking completeness. Do not use post-treatment variables as adjustment covariates.

## Control / treatment

Control: existing communication. Treatment: proactive delay notice + independently verifiable updated ETA + next steps/contact route. If a reliable ETA is unavailable, state that it is pending; never fabricate a date. Pricing, shipping priority and complaint adjudication remain the same across arms.

## Metrics and windows

Primary: fraction of all randomized customers whose index order has at least one waiting/non-receipt-related customer-initiated contact within 14 days of randomization. Use frozen human coding guidelines, blinded review and adjudication; do not rely on unvalidated AI topic labels. Multiple contacts count once. Denominator is all randomized customers (ITT), not only reviewers. Missing telemetry is missing, not automatically zero; establish a pre-launch completeness gate and report bounds for unresolved missing outcomes.

Secondary: any canonical low score <=2 for the index order recorded within 30 days of randomization / all randomized customers. Also report review response rate, time of answer relative to delivery, and respondent-only scores as descriptive measures. No review is not assumed to mean satisfaction. Timing-restricted respondent analyses are sensitivity checks, not the primary causal estimate.

Guardrails: unsubscribe / complaint rate, repeated contact burden, cancellation rate, notification cost per enrolled customer, and ETA accuracy. Pre-register acceptable operational margins with owners before launch; current data do not supply these margins. Survey burden and differential logging must be examined.

## Sample size logic: assumptions are not historical results

There is no same-definition historical primary baseline in the accepted Olist extracts. Obtain p0 from a separate pre-experiment logging pilot; do not estimate it from the treatment arm or substitute a review late rate. Select an absolute MDE δ based on operating value and messaging cost BEFORE randomization. Proposed planning settings: two-sided alpha=0.05, power=0.80, equal allocation. These are assumed experiment parameters.

For p1=p0-δ and pbar=(p0+p1)/2, normal approximation per arm:

```text
n ≈ [z(1-alpha/2)*sqrt(2*pbar*(1-pbar))
     + z(power)*sqrt(p0*(1-p0)+p1*(1-p1))]^2 / δ^2
```

Round up and account for documented missing telemetry; use simulation/exact planning when events are sparse. One index order per customer supports independent units; a future all-orders design would require cluster adjustment and a corresponding design effect. No numerical sample size is invented while p0 and δ are unknown. Reference: [statsmodels NormalIndPower](https://www.statsmodels.org/stable/generated/statsmodels.stats.power.NormalIndPower.html).

## Duration and statistical test

Proposed schedule: 4 weeks recruitment plus 30 days follow-up of the final cohort. Before launch, confirm projected eligible customer volume reaches planned sample size; otherwise revise duration prospectively. Do not extend merely because results are not significant. No repeated unadjusted significance peeking; safety stopping rules are pre-agreed.

Primary analysis: ITT risk difference with 95% CI, two-sided two-proportion test (stratum-adjusted estimate if blocked); exact test when sparse. Report absolute effect and uncertainty. One primary endpoint; secondary tests are exploratory or use a pre-registered multiplicity plan. Success requires a favorable, practically meaningful primary effect, acceptable guardrails and no material instrumentation bias. Reassess selection/response before claiming improved satisfaction.
