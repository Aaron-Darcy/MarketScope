import { nullable, required, type RowOf, type TableSpec } from './schema';

// Only the columns the site reads are declared. Nullability follows the dbt models: a column
// declared required that arrives null is a change upstream the pages were not written for.

export const dimBank = {
  cik: required('integer'),
  registrant_name: required('string'),
  rank: nullable('integer'),
  pinned_reason: nullable('string'),
  sic_description: required('string'),
  last_filed_period: required('date'),
  exit_type: nullable('string'),
  exit_date: nullable('date'),
  exit_counterparty: nullable('string'),
} satisfies TableSpec;

export const dimRateCycle = {
  cycle_key: required('integer'),
  cycle_name: nullable('string'),
  start_quarter: required('date'),
  end_quarter: required('date'),
  start_rate_fraction: required('number'),
  end_rate_fraction: required('number'),
  months: required('integer'),
} satisfies TableSpec;

export const bankEntityEvents = {
  cik: required('integer'),
  event_date: required('date'),
  event_type: required('string'),
  counterparty: nullable('string'),
  deposit_step: nullable('number'),
  material: nullable('boolean'),
  evidence_accession: required('string'),
  evidence_form: required('string'),
} satisfies TableSpec;

export const fctBankQuarter = {
  cik: required('integer'),
  quarter_end: required('date'),
  cost_of_deposits: nullable('number'),
  metric_tier: nullable('string'),
  interest_bearing_deposits: nullable('number'),
  noninterest_bearing_deposits: nullable('number'),
  policy_rate_fraction: nullable('number'),
  regulatory_cost_of_deposits: nullable('number'),
} satisfies TableSpec;

export const fctDepositBeta = {
  cik: required('integer'),
  cycle_name: required('string'),
  start_quarter: required('date'),
  measured_end_quarter: required('date'),
  partial_cycle: required('boolean'),
  metric_tier: nullable('string'),
  tier_changes_in_cycle: required('boolean'),
  start_cost_of_deposits: nullable('number'),
  end_cost_of_deposits: nullable('number'),
  start_rate_fraction: required('number'),
  end_rate_fraction: required('number'),
  deposit_beta: nullable('number'),
  material_event_in_cycle: required('boolean'),
} satisfies TableSpec;

export const martBankOverview = {
  cik: required('integer'),
  rank: nullable('integer'),
  exit_type: nullable('string'),
  exit_date: nullable('date'),
  first_cost_quarter: required('date'),
  last_cost_quarter: required('date'),
  cost_quarters: required('integer'),
  tier_1_share: required('number'),
  calibration_beta: nullable('number'),
  test_beta: nullable('number'),
  median_regulatory_gap_bp: nullable('number'),
} satisfies TableSpec;

export const martCrossBankComparison = {
  cik: required('integer'),
  calibration_beta: nullable('number'),
  test_beta: nullable('number'),
  calibration_tier: nullable('string'),
  test_tier: nullable('string'),
  in_headline: required('boolean'),
  in_r1: required('boolean'),
  in_r2: required('boolean'),
  in_r3: required('boolean'),
  in_r4: required('boolean'),
  calibration_rank: nullable('number'),
  test_rank: nullable('number'),
  calibration_quartile: nullable('integer'),
  test_quartile: nullable('integer'),
  quartile_shift: nullable('integer'),
  material_deviator: nullable('boolean'),
} satisfies TableSpec;

export const martPersistenceResult = {
  sample: required('string'),
  description: required('string'),
  filers: required('integer'),
  spearman: required('number'),
  p_value: required('number'),
  interval_low: required('number'),
  interval_high: required('number'),
  supported: required('boolean'),
} satisfies TableSpec;

export const martRecoveredBeta = {
  bank: required('string'),
  calibration_beta: required('number'),
  test_beta: required('number'),
  test_end: required('date'),
} satisfies TableSpec;

export const TABLES = {
  dim_bank: dimBank,
  dim_rate_cycle: dimRateCycle,
  bank_entity_events: bankEntityEvents,
  fct_bank_quarter: fctBankQuarter,
  fct_deposit_beta: fctDepositBeta,
  mart_bank_overview: martBankOverview,
  mart_cross_bank_comparison: martCrossBankComparison,
  mart_persistence_result: martPersistenceResult,
  mart_recovered_beta: martRecoveredBeta,
} as const;

export type TableName = keyof typeof TABLES;

export type Tables = { readonly [T in TableName]: readonly RowOf<(typeof TABLES)[T]>[] };

export type BankRow = RowOf<typeof dimBank>;
export type CycleRow = RowOf<typeof dimRateCycle>;
export type EventRow = RowOf<typeof bankEntityEvents>;
export type QuarterRow = RowOf<typeof fctBankQuarter>;
export type BetaRow = RowOf<typeof fctDepositBeta>;
export type OverviewRow = RowOf<typeof martBankOverview>;
export type ComparisonRow = RowOf<typeof martCrossBankComparison>;
export type ResultRow = RowOf<typeof martPersistenceResult>;
export type RecoveredRow = RowOf<typeof martRecoveredBeta>;
