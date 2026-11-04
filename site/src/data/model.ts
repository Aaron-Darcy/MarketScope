import { displayName } from './names';
import { median, quantile } from './stats';
import type {
  BetaRow,
  ComparisonRow,
  EventRow,
  OverviewRow,
  QuarterRow,
  RecoveredRow,
  ResultRow,
  Tables,
} from './tables';

export type CycleName = 'calibration' | 'test';

export interface Cycle {
  readonly name: CycleName;
  readonly years: string;
  readonly start: string;
  readonly end: string;
  readonly startRate: number;
  readonly endRate: number;
  readonly months: number;
}

export type Status = 'filing' | 'merged' | 'failed' | 'deregistered';

export interface Bank {
  readonly cik: number;
  readonly name: string;
  readonly rank: number | null;
  readonly pinnedReason: string | null;
  readonly sicDescription: string;
  readonly lastFiledPeriod: string;
  readonly status: Status;
  readonly exitDate: string | null;
  readonly exitCounterparty: string | null;
  readonly overview: OverviewRow;
  readonly comparison: ComparisonRow;
  readonly quarters: readonly QuarterRow[];
  readonly betas: Readonly<Partial<Record<CycleName, BetaRow>>>;
  readonly events: readonly EventRow[];
}

export type SampleCode = 'headline' | 'R1' | 'R2' | 'R3' | 'R4' | 'R4+recovered';

export interface Result extends ResultRow {
  readonly sample: SampleCode;
  readonly label: string;
}

export interface PolicyPoint {
  readonly quarter: string;
  readonly rate: number;
}

export interface Site {
  readonly banks: readonly Bank[];
  readonly bankByCik: ReadonlyMap<number, Bank>;
  readonly cycles: Readonly<Record<CycleName, Cycle>>;
  readonly policy: readonly PolicyPoint[];
  readonly results: readonly Result[];
  readonly headline: Result;
  readonly recovered: readonly RecoveredRow[];
  readonly quarters: readonly QuarterRow[];
}

/** A data inconsistency across tables that the pages cannot present honestly. */
export class ModelError extends Error {
  override name = 'ModelError';
}

const SAMPLE_LABELS: Readonly<Record<SampleCode, string>> = {
  headline: 'Headline: survivors only',
  R1: 'R1: tiers 1 and 2',
  R2: 'R2: acquirers inside a cycle',
  R3: 'R3: acquirers between cycles out',
  R4: 'R4: SVB added',
  'R4+recovered': 'R4 + First Republic, Signature',
};

const SAMPLE_ORDER: readonly SampleCode[] = ['headline', 'R1', 'R2', 'R3', 'R4', 'R4+recovered'];

const EXIT_STATUS: Readonly<Record<string, Status>> = {
  exit_merger: 'merged',
  failure: 'failed',
  exit_deregistration: 'deregistered',
};

const CYCLE_YEARS: Readonly<Record<CycleName, string>> = {
  calibration: '2015–2019',
  test: '2022–2023',
};

function isCycleName(value: string | null): value is CycleName {
  return value === 'calibration' || value === 'test';
}

function isSampleCode(value: string): value is SampleCode {
  return value in SAMPLE_LABELS;
}

function groupByCik<R extends { readonly cik: number }>(rows: readonly R[]): Map<number, R[]> {
  const groups = new Map<number, R[]>();
  for (const row of rows) {
    const group = groups.get(row.cik);
    if (group) group.push(row);
    else groups.set(row.cik, [row]);
  }
  return groups;
}

function oneByCik<R extends { readonly cik: number }>(
  rows: readonly R[],
  table: string,
): Map<number, R> {
  const byCik = new Map<number, R>();
  for (const row of rows) {
    if (byCik.has(row.cik)) throw new ModelError(`${table} repeats CIK ${row.cik}`);
    byCik.set(row.cik, row);
  }
  return byCik;
}

/** The federal funds path, one rate per quarter, which every bank-quarter must agree on. */
export function policySeries(quarters: readonly QuarterRow[]): PolicyPoint[] {
  const byQuarter = new Map<string, number>();
  for (const row of quarters) {
    if (row.policy_rate_fraction === null) continue;
    const seen = byQuarter.get(row.quarter_end);
    if (seen !== undefined && seen !== row.policy_rate_fraction) {
      throw new ModelError(`banks disagree on the policy rate for ${row.quarter_end}`);
    }
    byQuarter.set(row.quarter_end, row.policy_rate_fraction);
  }
  return [...byQuarter]
    .map(([quarter, rate]) => ({ quarter, rate }))
    .sort((a, b) => a.quarter.localeCompare(b.quarter));
}

export function buildSite(tables: Tables): Site {
  const overviews = oneByCik(tables.mart_bank_overview, 'mart_bank_overview');
  const comparisons = oneByCik(tables.mart_cross_bank_comparison, 'mart_cross_bank_comparison');
  const quarters = groupByCik(tables.fct_bank_quarter);
  const betas = groupByCik(tables.fct_deposit_beta);
  const events = groupByCik(tables.bank_entity_events);

  const banks = tables.dim_bank.map((row): Bank => {
    const overview = overviews.get(row.cik);
    const comparison = comparisons.get(row.cik);
    if (!overview || !comparison) {
      throw new ModelError(`CIK ${row.cik} is in dim_bank but missing from a mart`);
    }
    const status = row.exit_type === null ? 'filing' : EXIT_STATUS[row.exit_type];
    if (status === undefined) throw new ModelError(`unknown exit type ${String(row.exit_type)}`);

    const cycleBetas: Partial<Record<CycleName, BetaRow>> = {};
    for (const beta of betas.get(row.cik) ?? []) {
      if (!isCycleName(beta.cycle_name)) {
        throw new ModelError(`unknown cycle ${beta.cycle_name} for CIK ${row.cik}`);
      }
      cycleBetas[beta.cycle_name] = beta;
    }

    return {
      cik: row.cik,
      name: displayName(row.registrant_name),
      rank: row.rank,
      pinnedReason: row.pinned_reason,
      sicDescription: row.sic_description,
      lastFiledPeriod: row.last_filed_period,
      status,
      exitDate: row.exit_date,
      exitCounterparty: row.exit_counterparty,
      overview,
      comparison,
      quarters: (quarters.get(row.cik) ?? []).sort((a, b) =>
        a.quarter_end.localeCompare(b.quarter_end),
      ),
      betas: cycleBetas,
      events: (events.get(row.cik) ?? []).sort((a, b) => a.event_date.localeCompare(b.event_date)),
    };
  });
  const known = new Set(tables.dim_bank.map((row) => row.cik));
  for (const [table, ciks] of [
    ['mart_bank_overview', overviews.keys()],
    ['mart_cross_bank_comparison', comparisons.keys()],
    ['fct_bank_quarter', quarters.keys()],
    ['fct_deposit_beta', betas.keys()],
    ['bank_entity_events', events.keys()],
  ] as const) {
    for (const cik of ciks) {
      if (!known.has(cik))
        throw new ModelError(`${table} holds CIK ${String(cik)}, absent from dim_bank`);
    }
  }
  banks.sort((a, b) => (a.rank ?? Infinity) - (b.rank ?? Infinity) || a.name.localeCompare(b.name));

  const cycleRows = tables.dim_rate_cycle.filter((row) => row.cycle_name !== null);
  const cycles = Object.fromEntries(
    cycleRows.map((row) => {
      if (!isCycleName(row.cycle_name)) throw new ModelError(`unknown cycle ${row.cycle_name}`);
      const cycle: Cycle = {
        name: row.cycle_name,
        years: CYCLE_YEARS[row.cycle_name],
        start: row.start_quarter,
        end: row.end_quarter,
        startRate: row.start_rate_fraction,
        endRate: row.end_rate_fraction,
        months: row.months,
      };
      return [row.cycle_name, cycle];
    }),
  ) as Partial<Record<CycleName, Cycle>>;
  if (!cycles.calibration || !cycles.test) {
    throw new ModelError('dim_rate_cycle must name a calibration and a test cycle');
  }

  const results = tables.mart_persistence_result
    .map((row): Result => {
      if (!isSampleCode(row.sample)) throw new ModelError(`unknown sample ${row.sample}`);
      return { ...row, sample: row.sample, label: SAMPLE_LABELS[row.sample] };
    })
    .sort((a, b) => SAMPLE_ORDER.indexOf(a.sample) - SAMPLE_ORDER.indexOf(b.sample));
  const headline = results.find((result) => result.sample === 'headline');
  if (!headline) throw new ModelError('mart_persistence_result has no headline row');

  return {
    banks,
    bankByCik: new Map(banks.map((bank) => [bank.cik, bank])),
    cycles: { calibration: cycles.calibration, test: cycles.test },
    policy: policySeries(tables.fct_bank_quarter),
    results,
    headline,
    recovered: tables.mart_recovered_beta,
    quarters: tables.fct_bank_quarter,
  };
}

export type Membership = Exclude<SampleCode, 'R4+recovered'>;

/** Whether a bank is one of the filers in a pre-registered sample. */
export function inSample(bank: Bank, sample: Membership): boolean {
  const c = bank.comparison;
  switch (sample) {
    case 'headline':
      return c.in_headline;
    case 'R1':
      return c.in_r1;
    case 'R2':
      return c.in_r2;
    case 'R3':
      return c.in_r3;
    case 'R4':
      return c.in_r4;
  }
}

const EVENT_LABELS: Readonly<Record<string, string>> = {
  acquisition: 'Acquisition',
  reverse_acquisition: 'Reverse acquisition',
  exit_merger: 'Merged out',
  exit_deregistration: 'Deregistered',
  failure: 'Failure',
};

export function eventLabel(eventType: string): string {
  const label = EVENT_LABELS[eventType];
  if (label === undefined) throw new ModelError(`unknown entity event type ${eventType}`);
  return label;
}

export interface RankedBank {
  readonly bank: Bank;
  readonly calibrationBeta: number;
  readonly testBeta: number;
  readonly calibrationRank: number;
  readonly testRank: number;
  readonly calibrationQuartile: number;
  readonly testQuartile: number;
  readonly quartileShift: number;
  readonly materialDeviator: boolean;
}

/** The headline sample, each member carrying the betas, ranks and quartiles the test used. */
export function headlineSample(site: Site): RankedBank[] {
  return site.banks
    .filter((bank) => bank.comparison.in_headline)
    .map((bank) => {
      const c = bank.comparison;
      if (
        c.calibration_beta === null ||
        c.test_beta === null ||
        c.calibration_rank === null ||
        c.test_rank === null ||
        c.calibration_quartile === null ||
        c.test_quartile === null ||
        c.quartile_shift === null ||
        c.material_deviator === null
      ) {
        throw new ModelError(`${bank.name} is in the headline sample without a rank`);
      }
      return {
        bank,
        calibrationBeta: c.calibration_beta,
        testBeta: c.test_beta,
        calibrationRank: c.calibration_rank,
        testRank: c.test_rank,
        calibrationQuartile: c.calibration_quartile,
        testQuartile: c.test_quartile,
        quartileShift: c.quartile_shift,
        materialDeviator: c.material_deviator,
      };
    });
}

export interface Persistence {
  readonly banks: number;
  readonly stayedFastest: number;
  readonly sameQuartile: number;
  readonly movedTwo: number;
}

/** How many of the `top` fastest repricers in the first cycle were among the fastest again. */
export function persistenceSummary(sample: readonly RankedBank[], top = 6): Persistence {
  const cut = sample.length - top;
  return {
    banks: sample.length,
    stayedFastest: sample.filter((b) => b.calibrationRank > cut && b.testRank > cut).length,
    sameQuartile: sample.filter((b) => b.quartileShift === 0).length,
    movedTwo: sample.filter((b) => Math.abs(b.quartileShift) >= 2).length,
  };
}

/** Banks per cell, indexed [calibration quartile - 1][test quartile - 1]. */
export function quartileTransitions(sample: readonly RankedBank[]): number[][] {
  const quartiles = [1, 2, 3, 4];
  const outside = sample.find(
    (b) => !quartiles.includes(b.calibrationQuartile) || !quartiles.includes(b.testQuartile),
  );
  if (outside) throw new ModelError(`${outside.bank.name} has a quartile outside 1 to 4`);
  return quartiles.map((from) =>
    quartiles.map(
      (to) => sample.filter((b) => b.calibrationQuartile === from && b.testQuartile === to).length,
    ),
  );
}

export interface Validation {
  readonly pairs: number;
  readonly banks: number;
  readonly medianGapBp: number;
  readonly withinTenBp: number;
}

/** Tier 1 costs against the same bank's Call Report cost: the tag mapping's check. */
export function validationSummary(quarters: readonly QuarterRow[]): Validation {
  const pairs = validationPairs(quarters);
  const gaps = pairs.map((p) => Math.abs(p.filed - p.regulatory));
  return {
    pairs: pairs.length,
    banks: new Set(pairs.map((p) => p.cik)).size,
    medianGapBp: median(gaps) * 10_000,
    withinTenBp: gaps.filter((gap) => gap <= 0.001).length / gaps.length,
  };
}

export interface ValidationPair {
  readonly cik: number;
  readonly quarter: string;
  readonly filed: number;
  readonly regulatory: number;
}

export function validationPairs(quarters: readonly QuarterRow[]): ValidationPair[] {
  return quarters.flatMap((q) =>
    q.metric_tier === '1' && q.cost_of_deposits !== null && q.regulatory_cost_of_deposits !== null
      ? [
          {
            cik: q.cik,
            quarter: q.quarter_end,
            filed: q.cost_of_deposits,
            regulatory: q.regulatory_cost_of_deposits,
          },
        ]
      : [],
  );
}

export interface Coverage {
  readonly banks: number;
  readonly costQuarters: number;
  readonly tier1Share: number;
  readonly exited: number;
}

export function coverageSummary(site: Site): Coverage {
  const costed = site.quarters.filter((q) => q.cost_of_deposits !== null);
  return {
    banks: site.banks.length,
    costQuarters: costed.length,
    tier1Share: costed.filter((q) => q.metric_tier === '1').length / costed.length,
    exited: site.banks.filter((bank) => bank.status !== 'filing').length,
  };
}

export const TIER_LABELS = ['Tier 1', 'Tier 2', 'Tier 3', 'Tier X', 'Balance only'] as const;
export type TierLabel = (typeof TIER_LABELS)[number];

export function tierLabel(tier: string | null): TierLabel {
  switch (tier) {
    case '1':
      return 'Tier 1';
    case '2':
      return 'Tier 2';
    case '3':
      return 'Tier 3';
    case 'X':
      return 'Tier X';
    case null:
      return 'Balance only';
    default:
      throw new ModelError(`unknown metric tier ${tier}`);
  }
}

export function tierCounts(bank: Bank): Record<TierLabel, number> {
  const counts = Object.fromEntries(TIER_LABELS.map((label) => [label, 0])) as Record<
    TierLabel,
    number
  >;
  for (const q of bank.quarters) counts[tierLabel(q.metric_tier)] += 1;
  return counts;
}

export interface PeerBandPoint {
  readonly quarter: string;
  readonly low: number;
  readonly median: number;
  readonly high: number;
  readonly banks: number;
}

/**
 * The middle half of the universe's cost of deposits each quarter. Tier X is left out: it is a
 * reconstruction that failed its completeness check, and would widen the band with error.
 */
export function peerBand(quarters: readonly QuarterRow[], minimumBanks = 10): PeerBandPoint[] {
  const byQuarter = new Map<string, number[]>();
  for (const q of quarters) {
    if (q.cost_of_deposits === null || q.metric_tier === 'X') continue;
    const values = byQuarter.get(q.quarter_end);
    if (values) values.push(q.cost_of_deposits);
    else byQuarter.set(q.quarter_end, [q.cost_of_deposits]);
  }
  return [...byQuarter]
    .filter(([, values]) => values.length >= minimumBanks)
    .map(([quarter, values]) => ({
      quarter,
      low: quantile(values, 0.25),
      median: median(values),
      high: quantile(values, 0.75),
      banks: values.length,
    }))
    .sort((a, b) => a.quarter.localeCompare(b.quarter));
}

export interface PeerPosition {
  readonly cycle: CycleName;
  readonly beta: number;
  readonly slower: number;
  readonly others: number;
}

/** Where a bank's beta sits among every bank with a beta in the same cycle. */
export function peerPositions(site: Site, bank: Bank): PeerPosition[] {
  return (['calibration', 'test'] as const).flatMap((cycle) => {
    const own = bank.betas[cycle]?.deposit_beta;
    if (own === null || own === undefined) return [];
    const all = site.banks
      .map((b) => b.betas[cycle]?.deposit_beta)
      .filter((beta): beta is number => beta !== null && beta !== undefined);
    return [
      { cycle, beta: own, slower: all.filter((b) => b < own).length, others: all.length - 1 },
    ];
  });
}
