-- One row per universe member for the bank explorer: what the member is and how it left the
-- data, how much of its series resolves and at which tier, its beta in each study cycle with
-- the flags that qualify it, and how far its series agrees with its Call Reports.
--
-- The agreement is the median absolute gap over tier 1 quarters, the population methodology
-- 7.4 reports its error on, so a member's figure here is one observation of that
-- distribution rather than a different measure.

{{ config(materialized='table') }}

with coverage as (

    select
        cik,
        min(quarter_end) filter (where cost_of_deposits is not null) as first_cost_quarter,
        max(quarter_end) filter (where cost_of_deposits is not null) as last_cost_quarter,
        count(cost_of_deposits) as cost_quarters,
        count(*) filter (where metric_tier = '1') as tier_1_quarters,
        count(*) filter (where material_event) as material_events,
        median(abs(cost_of_deposits - regulatory_cost_of_deposits) * 10000)
            filter (where metric_tier = '1') as median_regulatory_gap_bp,
        count(regulatory_cost_of_deposits) filter (where metric_tier = '1')
            as regulatory_quarters,
        any_value(averaging_basis) as averaging_basis
    from {{ ref('fct_bank_quarter') }}
    group by cik

),

betas as (

    select
        cik,
        max(deposit_beta) filter (where cycle_name = 'calibration') as calibration_beta,
        max(metric_tier) filter (where cycle_name = 'calibration') as calibration_tier,
        bool_or(partial_cycle) filter (where cycle_name = 'calibration') as calibration_partial,
        bool_or(material_event_in_cycle) filter (where cycle_name = 'calibration')
            as calibration_material_event,
        max(deposit_beta) filter (where cycle_name = 'test') as test_beta,
        max(metric_tier) filter (where cycle_name = 'test') as test_tier,
        bool_or(partial_cycle) filter (where cycle_name = 'test') as test_partial,
        bool_or(material_event_in_cycle) filter (where cycle_name = 'test')
            as test_material_event
    from {{ ref('fct_deposit_beta') }}
    group by cik

)

select
    members.cik,
    members.registrant_name,
    members.rank,
    members.pinned,
    members.sic_description,
    members.is_terminal,
    members.last_filed_period,
    members.exit_type,
    members.exit_date,
    members.exit_counterparty,
    coverage.first_cost_quarter,
    coverage.last_cost_quarter,
    coverage.cost_quarters,
    coverage.tier_1_quarters,
    coverage.tier_1_quarters / nullif(coverage.cost_quarters, 0) as tier_1_share,
    coverage.material_events,
    betas.calibration_beta,
    betas.calibration_tier,
    betas.calibration_partial,
    betas.calibration_material_event,
    betas.test_beta,
    betas.test_tier,
    betas.test_partial,
    betas.test_material_event,
    coverage.regulatory_quarters,
    coverage.median_regulatory_gap_bp,
    coverage.averaging_basis
from {{ ref('dim_bank') }} as members
left join coverage using (cik)
left join betas using (cik)
