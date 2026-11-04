import { dollars, percent, quarterLabel } from '../data/format';
import {
  TIER_LABELS,
  tierCounts,
  tierLabel,
  type Bank,
  type Cycle,
  type CycleName,
  type PeerBandPoint,
  type PolicyPoint,
} from '../data/model';
import { baseOption, tooltipBase, itemTooltip, tooltipHtml, valueX, valueY } from './base';
import { cycleAreas, quarterAxis, type Built } from './shared';
import type { ChartTheme } from './theme';

function byQuarter<T>(rows: readonly T[], key: (row: T) => string): Map<string, T> {
  return new Map(rows.map((row) => [key(row), row]));
}

/**
 * The bank's cost of deposits from its filings and from its Call Reports, against the federal
 * funds rate and the middle half of every bank's cost that quarter.
 */
export function costAgainstPolicy(
  bank: Bank,
  policy: readonly PolicyPoint[],
  band: readonly PeerBandPoint[],
  cycles: Readonly<Record<CycleName, Cycle>>,
  theme: ChartTheme,
): Built {
  const quarters = [
    ...new Set([...policy.map((p) => p.quarter), ...bank.quarters.map((q) => q.quarter_end)]),
  ].sort();
  const rates = byQuarter(policy, (p) => p.quarter);
  const own = byQuarter(bank.quarters, (q) => q.quarter_end);
  const peers = byQuarter(band, (p) => p.quarter);
  const first = bank.quarters.find((q) => q.cost_of_deposits !== null)?.quarter_end;
  const startIndex = first ? Math.max(0, quarters.indexOf(first) - 2) : 0;

  return {
    option: {
      ...baseOption(theme),
      grid: { left: 52, right: 20, top: 40, bottom: 96 },
      legend: {
        top: 0,
        left: 0,
        itemWidth: 14,
        itemHeight: 8,
        textStyle: { color: theme.secondary, fontSize: 12 },
        data: [
          { name: 'From its SEC filings', icon: 'roundRect' },
          { name: 'From its Call Reports', icon: 'roundRect' },
          { name: 'Federal funds rate', icon: 'roundRect' },
          { name: 'Middle half of all banks', icon: 'rect' },
        ],
      },
      tooltip: {
        ...tooltipBase(theme),
        trigger: 'axis',
        axisPointer: { type: 'line', lineStyle: { color: theme.axis } },
        formatter: itemTooltip((_s, i) => {
          const quarter = quarters[i];
          if (quarter === undefined) return null;
          const q = own.get(quarter);
          const p = peers.get(quarter);
          return tooltipHtml(quarterLabel(quarter), [
            {
              label: 'from its SEC filings',
              value: percent(q?.cost_of_deposits ?? null, 2),
              color: theme.blue,
            },
            {
              label: 'from its Call Reports',
              value: percent(q?.regulatory_cost_of_deposits ?? null, 2),
              color: theme.orange,
            },
            {
              label: 'federal funds rate',
              value: percent(rates.get(quarter)?.rate ?? null, 2),
              color: theme.secondary,
            },
            {
              label: 'middle half of all banks',
              value: p ? `${percent(p.low, 2)} to ${percent(p.high, 2)}` : '–',
            },
          ]);
        }),
      },
      xAxis: quarterAxis(theme, quarters),
      yAxis: valueY(theme, { percent: true }),
      dataZoom: [
        { type: 'inside', startValue: startIndex },
        {
          type: 'slider',
          startValue: startIndex,
          height: 28,
          bottom: 24,
          borderColor: theme.grid,
          fillerColor: theme.wash,
          handleStyle: { color: theme.surface, borderColor: theme.axis },
          dataBackground: { lineStyle: { color: theme.axis }, areaStyle: { color: theme.grid } },
          textStyle: { color: theme.muted },
          labelFormatter: (_value: number, text: string) => quarterLabel(text),
        },
      ],
      series: [
        {
          name: 'Band floor',
          type: 'line',
          stack: 'band',
          data: quarters.map((q) => peers.get(q)?.low ?? null),
          symbol: 'none',
          lineStyle: { opacity: 0 },
          silent: true,
          tooltip: { show: false },
        },
        {
          name: 'Middle half of all banks',
          type: 'line',
          stack: 'band',
          data: quarters.map((q) => {
            const p = peers.get(q);
            return p ? p.high - p.low : null;
          }),
          symbol: 'none',
          lineStyle: { opacity: 0 },
          areaStyle: { color: theme.wash },
          itemStyle: { color: theme.wash },
          silent: true,
          markArea: cycleAreas(theme, cycles),
        },
        {
          name: 'Federal funds rate',
          type: 'line',
          data: quarters.map((q) => rates.get(q)?.rate ?? null),
          symbol: 'none',
          lineStyle: { color: theme.grey, width: 2 },
          itemStyle: { color: theme.grey },
        },
        {
          name: 'From its Call Reports',
          type: 'line',
          data: quarters.map((q) => own.get(q)?.regulatory_cost_of_deposits ?? null),
          symbol: 'none',
          lineStyle: { color: theme.orange, width: 2 },
          itemStyle: { color: theme.orange },
        },
        {
          name: 'From its SEC filings',
          type: 'line',
          data: quarters.map((q) => own.get(q)?.cost_of_deposits ?? null),
          symbol: 'none',
          lineStyle: { color: theme.blue, width: 2.5 },
          itemStyle: { color: theme.blue },
          z: 3,
        },
      ],
    },
  };
}

interface StripDot {
  readonly bank: Bank;
  readonly beta: number;
  readonly row: number;
}

/** Every bank's beta in each cycle, the chosen one drawn large; other dots link to their bank. */
export function peerStrip(banks: readonly Bank[], focus: Bank, theme: ChartTheme): Built {
  const cycles: readonly CycleName[] = ['calibration', 'test'];
  const dots: StripDot[] = cycles.flatMap((cycle, row) =>
    banks.flatMap((bank) => {
      const beta = bank.betas[cycle]?.deposit_beta;
      return beta === null || beta === undefined ? [] : [{ bank, beta, row }];
    }),
  );
  // A fixed jitter from the CIK keeps each bank in the same place on every visit.
  const jitter = (cik: number) => (((cik * 7919) % 41) - 20) / 80;
  const others = dots.filter((d) => d.bank.cik !== focus.cik);
  const own = dots.filter((d) => d.bank.cik === focus.cik);
  const groups = [others, own];
  const at = (s: number, i: number) => groups[s]?.[i];

  return {
    option: {
      ...baseOption(theme),
      grid: { left: 96, right: 24, top: 12, bottom: 48 },
      tooltip: {
        ...tooltipBase(theme),
        trigger: 'item',
        formatter: itemTooltip((s, i) => {
          const d = at(s, i);
          return d
            ? tooltipHtml(d.bank.name, [
                { label: d.row === 0 ? '2015–19 beta' : '2022–23 beta', value: d.beta.toFixed(3) },
              ])
            : null;
        }),
      },
      xAxis: valueX(theme, { name: 'Deposit beta', min: 0, max: 1, gap: 28 }),
      yAxis: {
        type: 'value',
        min: -0.5,
        max: 1.5,
        interval: 0.5,
        axisLabel: {
          color: theme.ink,
          formatter: (v: number) => (v === 0 ? '2015–2019' : v === 1 ? '2022–2023' : ''),
        },
        splitLine: { show: false },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      series: [
        {
          type: 'scatter',
          symbolSize: 10,
          cursor: 'pointer',
          itemStyle: {
            color: theme.grey,
            opacity: 0.85,
            borderColor: theme.surface,
            borderWidth: 1,
          },
          data: others.map((d) => [d.beta, d.row + jitter(d.bank.cik)]),
        },
        {
          type: 'scatter',
          symbolSize: 20,
          itemStyle: { color: theme.orange, borderColor: theme.surface, borderWidth: 2 },
          data: own.map((d) => [d.beta, d.row]),
          label: {
            show: true,
            position: 'top',
            distance: 6,
            color: theme.ink,
            fontWeight: 600,
            formatter: ({ dataIndex }) => own[dataIndex]?.beta.toFixed(2) ?? '',
          },
          z: 3,
        },
      ],
    },
    bankAt: (s, i) => at(s, i)?.bank,
  };
}

/** The comparability tier of each quarter the bank filed, as a strip of coloured cells. */
export function tierStrip(bank: Bank, theme: ChartTheme): Built {
  const quarters = bank.quarters.map((q) => q.quarter_end);
  const tiers = bank.quarters.map((q) => tierLabel(q.metric_tier));
  const present = TIER_LABELS.filter((label) => tiers.includes(label));
  return {
    option: {
      ...baseOption(theme),
      grid: { left: 8, right: 8, top: 36, bottom: 28 },
      legend: {
        top: 0,
        left: 0,
        icon: 'rect',
        itemWidth: 12,
        itemHeight: 12,
        textStyle: { color: theme.secondary, fontSize: 12 },
        data: [...present],
      },
      tooltip: {
        ...tooltipBase(theme),
        trigger: 'item',
        formatter: itemTooltip((_s, i) => {
          const quarter = quarters[i];
          const tier = tiers[i];
          return quarter && tier
            ? tooltipHtml(quarterLabel(quarter), [{ label: 'tier', value: tier }])
            : null;
        }),
      },
      xAxis: { ...quarterAxis(theme, quarters), boundaryGap: true },
      yAxis: { type: 'value', show: false, max: 1 },
      series: present.map((label) => ({
        name: label,
        type: 'bar' as const,
        stack: 'tier',
        barCategoryGap: '12%',
        itemStyle: { color: theme.tiers[label], borderRadius: 2 },
        data: tiers.map((tier) => (tier === label ? 1 : null)),
      })),
    },
  };
}

/** Interest-bearing and non-interest-bearing deposits, stacked to the deposit base. */
export function depositsArea(bank: Bank, theme: ChartTheme): Built {
  const rows = bank.quarters.filter(
    (q) => q.interest_bearing_deposits !== null || q.noninterest_bearing_deposits !== null,
  );
  const quarters = rows.map((q) => q.quarter_end);
  const series = [
    ['Interest-bearing', theme.blue, rows.map((q) => q.interest_bearing_deposits)],
    ['Non-interest-bearing', theme.aqua, rows.map((q) => q.noninterest_bearing_deposits)],
  ] as const;
  return {
    option: {
      ...baseOption(theme),
      grid: { left: 64, right: 20, top: 40, bottom: 32 },
      legend: {
        top: 0,
        left: 0,
        icon: 'rect',
        itemWidth: 12,
        itemHeight: 12,
        textStyle: { color: theme.secondary, fontSize: 12 },
        data: series.map(([name]) => name),
      },
      tooltip: {
        ...tooltipBase(theme),
        trigger: 'axis',
        axisPointer: { type: 'line', lineStyle: { color: theme.axis } },
        formatter: itemTooltip((_s, i) => {
          const q = rows[i];
          if (!q) return null;
          return tooltipHtml(
            quarterLabel(q.quarter_end),
            series.map(([name, color, values]) => {
              const value = values[i];
              return {
                label: name.toLowerCase(),
                value: value == null ? '–' : dollars(value),
                color,
              };
            }),
          );
        }),
      },
      xAxis: quarterAxis(theme, quarters),
      yAxis: valueY(theme, { format: dollars }),
      series: series.map(([name, color, values]) => ({
        name,
        type: 'line' as const,
        stack: 'deposits',
        symbol: 'none',
        lineStyle: { color, width: 2 },
        itemStyle: { color },
        areaStyle: { color, opacity: 0.18 },
        data: [...values],
      })),
    },
  };
}

/** Quarters at each comparability tier, one bar per bank. */
export function coverageBars(banks: readonly Bank[], theme: ChartTheme): Built {
  const counts = banks.map(tierCounts);
  return {
    option: {
      ...baseOption(theme),
      grid: { left: 180, right: 24, top: 36, bottom: 40 },
      legend: {
        top: 0,
        left: 0,
        icon: 'rect',
        itemWidth: 12,
        itemHeight: 12,
        textStyle: { color: theme.secondary, fontSize: 12 },
        data: [...TIER_LABELS],
      },
      tooltip: {
        ...tooltipBase(theme),
        trigger: 'item',
        formatter: itemTooltip((_s, i) => {
          const bank = banks[i];
          const c = counts[i];
          return bank && c
            ? tooltipHtml(
                bank.name,
                TIER_LABELS.filter((label) => c[label] > 0).map((label) => ({
                  label: label.toLowerCase(),
                  value: `${String(c[label])} quarters`,
                  color: theme.tiers[label],
                })),
              )
            : null;
        }),
      },
      xAxis: valueX(theme, { name: 'Quarters', gap: 26 }),
      yAxis: {
        type: 'category',
        inverse: true,
        data: banks.map((b) => b.name),
        axisTick: { show: false },
        axisLine: { show: false },
        axisLabel: { color: theme.ink, fontSize: 11 },
      },
      series: TIER_LABELS.map((label) => ({
        name: label,
        type: 'bar' as const,
        stack: 'quarters',
        barWidth: 12,
        cursor: 'pointer',
        itemStyle: { color: theme.tiers[label], borderColor: theme.surface, borderWidth: 1 },
        data: counts.map((c) => c[label]),
      })),
    },
    bankAt: (_s, i) => banks[i],
  };
}
