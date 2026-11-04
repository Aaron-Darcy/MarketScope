import { readFile } from 'node:fs/promises';

import { beforeAll, describe, expect, it } from 'vitest';

import {
  buildSite,
  coverageSummary,
  eventLabel,
  headlineSample,
  inSample,
  ModelError,
  peerBand,
  peerPositions,
  persistenceSummary,
  policySeries,
  quartileTransitions,
  tierLabel,
  validationSummary,
  type Site,
} from './model';
import { readTables } from './parquet';
import { linearFit } from './stats';
import type { QuarterRow, Tables } from './tables';

async function readExport(): Promise<Tables> {
  return readTables(async (table) => {
    const bytes = await readFile(new URL(`../../../data/site/${table}.parquet`, import.meta.url));
    return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
  });
}

// The expected figures are those the Evidence site's SQL computed from the same export,
// and those methodology 6.1 reports, so the port is held to what was already published.
describe('the committed export', () => {
  let tables: Tables;
  let site: Site;

  beforeAll(async () => {
    tables = await readExport();
    site = buildSite(tables);
  });

  it('joins every bank to its marts', () => {
    expect(site.banks).toHaveLength(51);
    expect(site.banks[0]?.name).toBe('JPMorgan Chase');
    expect(site.banks.at(-1)?.rank).toBeNull();
  });

  it('carries the pre-registered headline', () => {
    expect(site.headline.filers).toBe(22);
    expect(site.headline.spearman.toFixed(3)).toBe('0.590');
    expect(site.results.map((r) => r.sample)).toEqual([
      'headline',
      'R1',
      'R2',
      'R3',
      'R4',
      'R4+recovered',
    ]);
  });

  it('reproduces the headline sample summary', () => {
    const sample = headlineSample(site);
    expect(persistenceSummary(sample)).toEqual({
      banks: 22,
      stayedFastest: 5,
      sameQuartile: 11,
      movedTwo: 3,
    });
    expect(quartileTransitions(sample)).toEqual([
      [2, 1, 2, 0],
      [2, 3, 1, 0],
      [1, 2, 1, 1],
      [0, 0, 1, 5],
    ]);
    const fit = linearFit(sample.map((b) => [b.calibrationBeta, b.testBeta]));
    expect(fit.pearson).toBeCloseTo(0.597485011676579, 12);
    expect(fit.slope).toBeCloseTo(0.7232086291833268, 12);
  });

  it('reproduces the Call Report validation', () => {
    const validation = validationSummary(site.quarters);
    expect(validation.pairs).toBe(1948);
    expect(validation.banks).toBe(35);
    expect(validation.medianGapBp).toBeCloseTo(1.1453495341812863, 10);
    expect(validation.withinTenBp).toBeCloseTo(0.8711498973305954, 12);
  });

  it('reproduces the coverage figures', () => {
    const coverage = coverageSummary(site);
    expect(coverage).toMatchObject({ banks: 51, costQuarters: 3066, exited: 11 });
    expect(coverage.tier1Share).toBeCloseTo(2323 / 3066, 12);
  });

  it('places as many filers in each sample as its result counts', () => {
    for (const sample of ['headline', 'R1', 'R2', 'R3', 'R4'] as const) {
      const result = site.results.find((r) => r.sample === sample);
      expect(site.banks.filter((bank) => inSample(bank, sample)).length).toBe(result?.filers);
    }
  });

  it('labels every entity event in the export', () => {
    for (const bank of site.banks) {
      for (const event of bank.events) expect(eventLabel(event.event_type)).toBeTruthy();
    }
  });

  it('has one policy rate per quarter', () => {
    expect(site.policy).toHaveLength(73);
  });

  it('places a bank among its peers', () => {
    const jpm = site.bankByCik.get(19617);
    if (!jpm) throw new Error('JPMorgan Chase is missing');
    const positions = peerPositions(site, jpm);
    expect(positions.map((p) => [p.cycle, p.others])).toEqual([
      ['calibration', 44],
      ['test', 43],
    ]);
  });

  it('builds a peer band only where enough banks report', () => {
    const band = peerBand(site.quarters);
    expect(band.every((p) => p.banks >= 10 && p.low <= p.median && p.median <= p.high)).toBe(true);
  });
});

describe('inconsistent tables', () => {
  let tables: Tables;

  beforeAll(async () => {
    tables = await readExport();
  });

  it('are refused when a bank is missing from a mart', () => {
    const broken = { ...tables, mart_bank_overview: tables.mart_bank_overview.slice(1) };
    expect(() => buildSite(broken)).toThrow(ModelError);
  });

  it('are refused when a fact belongs to no bank', () => {
    const [first, ...rest] = tables.fct_bank_quarter;
    if (!first) throw new Error('no quarters');
    const broken = { ...tables, fct_bank_quarter: [{ ...first, cik: 1 }, ...rest] };
    expect(() => buildSite(broken)).toThrow('fct_bank_quarter holds CIK 1, absent from dim_bank');
  });

  it('are refused when a sample is not one the site knows', () => {
    const [first, ...rest] = tables.mart_persistence_result;
    if (!first) throw new Error('no results');
    const broken = { ...tables, mart_persistence_result: [{ ...first, sample: 'R9' }, ...rest] };
    expect(() => buildSite(broken)).toThrow('unknown sample R9');
  });

  it('are refused when the headline row is missing', () => {
    const broken = {
      ...tables,
      mart_persistence_result: tables.mart_persistence_result.filter(
        (r) => r.sample !== 'headline',
      ),
    };
    expect(() => buildSite(broken)).toThrow('no headline row');
  });
});

describe('policySeries', () => {
  const quarter = (cik: number, rate: number): QuarterRow => ({
    cik,
    quarter_end: '2022-03-31',
    cost_of_deposits: null,
    metric_tier: null,
    interest_bearing_deposits: null,
    noninterest_bearing_deposits: null,
    policy_rate_fraction: rate,
    regulatory_cost_of_deposits: null,
  });

  it('refuses banks that disagree on the rate for a quarter', () => {
    expect(() => policySeries([quarter(1, 0.01), quarter(2, 0.02)])).toThrow(ModelError);
  });
});

describe('eventLabel', () => {
  it('refuses an event type the pages do not describe', () => {
    expect(eventLabel('failure')).toBe('Failure');
    expect(() => eventLabel('spin_off')).toThrow(ModelError);
  });
});

describe('tierLabel', () => {
  it('refuses a tier the site has no colour for', () => {
    expect(tierLabel(null)).toBe('Balance only');
    expect(() => tierLabel('4')).toThrow(ModelError);
  });
});
