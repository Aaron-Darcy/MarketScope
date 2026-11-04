import { quarterLabel, percent, signed, pValue } from '../data/format';
import type {
  Bank,
  Cycle,
  CycleName,
  PolicyPoint,
  RankedBank,
  Result,
  ValidationPair,
} from '../data/model';
import {
  baseOption,
  tooltipBase,
  diagonal,
  itemTooltip,
  legend,
  tooltipHtml,
  valueX,
  valueY,
} from './base';
import { cycleAreas, niceBounds, quarterAxis, type Built } from './shared';
import type { ChartTheme } from './theme';

const ring = (theme: ChartTheme) => ({ borderColor: theme.surface, borderWidth: 2 });

// A direct label sits over other banks' dots; backing it with the surface keeps it legible.
const labelBacking = (theme: ChartTheme) => ({
  backgroundColor: theme.surface,
  padding: [2, 5],
  borderRadius: 4,
});

function betaTooltip(
  theme: ChartTheme,
  name: string,
  calibration: number,
  test: number,
  note?: string,
) {
  return tooltipHtml(
    name,
    [
      { label: '2015–19 beta', value: calibration.toFixed(3), color: theme.blue },
      { label: '2022–23 beta', value: test.toFixed(3), color: theme.orange },
    ],
    note,
  );
}

/** Each headline bank's beta in one cycle against the next; the ones that moved are named. */
export function crossCycleScatter(sample: readonly RankedBank[], theme: ChartTheme): Built {
  const kept = sample.filter((b) => !b.materialDeviator);
  const moved = sample.filter((b) => b.materialDeviator);
  const groups = [kept, moved];
  const [low, high] = niceBounds(sample.flatMap((b) => [b.calibrationBeta, b.testBeta]));
  const at = (series: number, index: number) => groups[series - 1]?.[index];

  return {
    option: {
      ...baseOption(theme),
      grid: { left: 56, right: 24, top: 16, bottom: 72 },
      tooltip: {
        ...tooltipBase(theme),
        trigger: 'item',
        formatter: itemTooltip((s, i) => {
          const b = at(s, i);
          return b ? betaTooltip(theme, b.bank.name, b.calibrationBeta, b.testBeta) : null;
        }),
      },
      legend: legend(theme, ['Kept its place, within a quartile', 'Moved two quartiles or more']),
      xAxis: valueX(theme, { name: 'Deposit beta, 2015–2019', min: low, max: high }),
      yAxis: valueY(theme, { name: 'Deposit beta, 2022–2023', min: low, max: high, gap: 40 }),
      series: [
        diagonal(theme, low, high),
        {
          name: 'Kept its place, within a quartile',
          type: 'scatter',
          symbolSize: 13,
          itemStyle: { color: theme.blue, ...ring(theme) },
          cursor: 'pointer',
          data: kept.map((b) => [b.calibrationBeta, b.testBeta]),
        },
        {
          name: 'Moved two quartiles or more',
          type: 'scatter',
          symbolSize: 13,
          itemStyle: { color: theme.orange, ...ring(theme) },
          cursor: 'pointer',
          data: moved.map((b) => [b.calibrationBeta, b.testBeta]),
          label: {
            show: true,
            position: 'right',
            distance: 8,
            color: theme.ink,
            fontWeight: 600,
            ...labelBacking(theme),
            formatter: ({ dataIndex }) => moved[dataIndex]?.bank.name ?? '',
          },
        },
      ],
    },
    bankAt: (s, i) => at(s, i)?.bank,
  };
}

/** Each pre-registered sample's correlation with its 95 percent interval. */
export function forestPlot(results: readonly Result[], theme: ChartTheme): Built {
  return {
    option: {
      ...baseOption(theme),
      grid: { left: 240, right: 32, top: 12, bottom: 48 },
      tooltip: {
        ...tooltipBase(theme),
        trigger: 'item',
        formatter: itemTooltip((_s, i) => {
          const r = results[i];
          return r
            ? tooltipHtml(
                r.label,
                [
                  { label: 'Spearman', value: signed(r.spearman, 3) },
                  {
                    label: '95% interval',
                    value: `${signed(r.interval_low, 2)} to ${signed(r.interval_high, 2)}`,
                  },
                  { label: 'one-sided p', value: pValue(r.p_value) },
                  { label: 'banks', value: String(r.filers) },
                ],
                r.description,
              )
            : null;
        }),
      },
      xAxis: valueX(theme, {
        name: 'Rank correlation and 95% interval; zero is no relationship',
        min: -0.2,
        max: 1,
        gap: 28,
      }),
      yAxis: {
        type: 'category',
        inverse: true,
        data: results.map((r) => `${r.label}  (${String(r.filers)})`),
        axisLabel: { color: theme.ink, fontSize: 12 },
        axisTick: { show: false },
        axisLine: { show: false },
      },
      series: [
        {
          type: 'custom',
          silent: true,
          renderItem: (params, api) => {
            const index = params.dataIndex;
            const from = api.coord([api.value(0), index]);
            const to = api.coord([api.value(1), index]);
            return {
              type: 'line',
              shape: { x1: from[0], y1: from[1], x2: to[0], y2: to[1] },
              style: {
                stroke: index === 0 ? theme.blue : theme.grey,
                lineWidth: 3,
                lineCap: 'round',
              },
            };
          },
          encode: { x: [0, 1], y: 2 },
          data: results.map((r, i) => [r.interval_low, r.interval_high, i]),
          z: 1,
        },
        {
          type: 'scatter',
          symbolSize: 14,
          data: results.map((r, i) => ({
            value: [r.spearman, i],
            itemStyle: { color: i === 0 ? theme.blue : theme.aqua, ...ring(theme) },
          })),
          label: {
            show: true,
            position: 'top',
            color: theme.ink,
            fontSize: 11,
            formatter: ({ dataIndex }) => {
              const r = results[dataIndex];
              return r ? signed(r.spearman, 2) : '';
            },
          },
          markLine: {
            silent: true,
            symbol: 'none',
            label: { show: false },
            lineStyle: { color: theme.secondary, type: 'solid', width: 1 },
            data: [{ xAxis: 0 }],
          },
          z: 2,
        },
      ],
    },
  };
}

/** The federal funds path with the two cycles the study compares shaded. */
export function ratePath(
  policy: readonly PolicyPoint[],
  cycles: Readonly<Record<CycleName, Cycle>>,
  theme: ChartTheme,
): Built {
  const quarters = policy.map((p) => p.quarter);
  return {
    option: {
      ...baseOption(theme),
      grid: { left: 52, right: 20, top: 36, bottom: 32 },
      tooltip: {
        ...tooltipBase(theme),
        trigger: 'axis',
        axisPointer: { type: 'line', lineStyle: { color: theme.axis } },
        formatter: itemTooltip((_s, i) => {
          const p = policy[i];
          return p
            ? tooltipHtml(quarterLabel(p.quarter), [
                { label: 'federal funds, quarterly average', value: percent(p.rate, 2) },
              ])
            : null;
        }),
      },
      xAxis: quarterAxis(theme, quarters),
      yAxis: valueY(theme, { percent: true }),
      series: [
        {
          name: 'Federal funds rate',
          type: 'line',
          data: policy.map((p) => p.rate),
          symbol: 'none',
          lineStyle: { color: theme.blue, width: 2 },
          areaStyle: { color: theme.wash },
          markArea: cycleAreas(theme, cycles),
        },
      ],
    },
  };
}

/** Ranks rather than betas, so a level shift between the cycles drops out. */
export function rankScatter(sample: readonly RankedBank[], theme: ChartTheme): Built {
  const n = sample.length;
  const groups: [string, string, RankedBank[]][] = [
    ['Same quartile', theme.blue, sample.filter((b) => b.quartileShift === 0)],
    ['One quartile apart', theme.grey, sample.filter((b) => Math.abs(b.quartileShift) === 1)],
    ['Two or more apart', theme.orange, sample.filter((b) => Math.abs(b.quartileShift) >= 2)],
  ];
  const at = (s: number, i: number) => groups[s - 1]?.[2][i];
  return {
    option: {
      ...baseOption(theme),
      grid: { left: 56, right: 24, top: 16, bottom: 72 },
      tooltip: {
        ...tooltipBase(theme),
        trigger: 'item',
        formatter: itemTooltip((s, i) => {
          const b = at(s, i);
          return b
            ? tooltipHtml(b.bank.name, [
                { label: `rank of ${String(n)}, 2015–19`, value: String(b.calibrationRank) },
                { label: `rank of ${String(n)}, 2022–23`, value: String(b.testRank) },
              ])
            : null;
        }),
      },
      legend: legend(
        theme,
        groups.map(([name]) => name),
      ),
      xAxis: valueX(theme, { name: 'Rank in 2015–2019, 1 the slowest', min: 0, max: n + 1 }),
      yAxis: valueY(theme, { name: 'Rank in 2022–2023', min: 0, max: n + 1, gap: 30 }),
      series: [
        diagonal(theme, 0, n + 1),
        ...groups.map(([name, color, banks], index) => ({
          name,
          type: 'scatter' as const,
          symbolSize: 13,
          cursor: 'pointer',
          itemStyle: { color, ...ring(theme) },
          data: banks.map((b) => [b.calibrationRank, b.testRank]),
          label: {
            show: index === 2,
            position: 'right' as const,
            color: theme.ink,
            fontWeight: 600,
            ...labelBacking(theme),
            formatter: ({ dataIndex }: { dataIndex: number }) => banks[dataIndex]?.bank.name ?? '',
          },
        })),
      ],
    },
    bankAt: (s, i) => at(s, i)?.bank,
  };
}

export interface SurvivorPoint {
  readonly name: string;
  readonly calibrationBeta: number;
  readonly testBeta: number;
  readonly failed: boolean;
  readonly note?: string;
  readonly bank?: Bank;
}

/** The R4 sample with the failed banks recovered from their Call Reports added. */
export function survivorshipScatter(points: readonly SurvivorPoint[], theme: ChartTheme): Built {
  const groups = [points.filter((p) => !p.failed), points.filter((p) => p.failed)];
  const [low, high] = niceBounds(points.flatMap((p) => [p.calibrationBeta, p.testBeta]));
  const at = (s: number, i: number) => groups[s - 1]?.[i];
  return {
    option: {
      ...baseOption(theme),
      grid: { left: 56, right: 24, top: 16, bottom: 72 },
      tooltip: {
        ...tooltipBase(theme),
        trigger: 'item',
        formatter: itemTooltip((s, i) => {
          const p = at(s, i);
          return p ? betaTooltip(theme, p.name, p.calibrationBeta, p.testBeta, p.note) : null;
        }),
      },
      legend: legend(theme, ['Kept filing', 'Failed']),
      xAxis: valueX(theme, { name: 'Deposit beta, 2015–2019', min: low, max: high }),
      yAxis: valueY(theme, { name: 'Deposit beta, 2022–2023', min: low, max: high, gap: 40 }),
      series: [
        diagonal(theme, low, high),
        {
          name: 'Kept filing',
          type: 'scatter',
          symbolSize: 12,
          cursor: 'pointer',
          itemStyle: { color: theme.blue, opacity: 0.8, ...ring(theme) },
          data: groups[0]?.map((p) => [p.calibrationBeta, p.testBeta]) ?? [],
        },
        {
          name: 'Failed',
          type: 'scatter',
          symbolSize: 16,
          itemStyle: { color: theme.orange, ...ring(theme) },
          data: groups[1]?.map((p) => [p.calibrationBeta, p.testBeta]) ?? [],
          label: {
            show: true,
            position: 'right',
            distance: 8,
            color: theme.ink,
            fontWeight: 600,
            ...labelBacking(theme),
            formatter: ({ dataIndex }) => groups[1]?.[dataIndex]?.name ?? '',
          },
        },
      ],
    },
    bankAt: (s, i) => at(s, i)?.bank,
  };
}

/** Every tier 1 bank-quarter: the cost from XBRL tags against the same bank's Call Reports. */
export function validationScatter(
  pairs: readonly ValidationPair[],
  nameOf: (cik: number) => string,
  theme: ChartTheme,
): Built {
  const high = Math.ceil(Math.max(...pairs.flatMap((p) => [p.filed, p.regulatory])) * 100) / 100;
  return {
    option: {
      ...baseOption(theme),
      grid: { left: 64, right: 24, top: 16, bottom: 56 },
      tooltip: {
        ...tooltipBase(theme),
        trigger: 'item',
        formatter: itemTooltip((_s, i) => {
          const p = pairs[i];
          return p
            ? tooltipHtml(`${nameOf(p.cik)}, ${quarterLabel(p.quarter)}`, [
                { label: 'from SEC filings', value: percent(p.filed, 2) },
                { label: 'from Call Reports', value: percent(p.regulatory, 2) },
                {
                  label: 'gap',
                  value: `${(Math.abs(p.filed - p.regulatory) * 10_000).toFixed(1)} bp`,
                },
              ])
            : null;
        }),
      },
      xAxis: valueX(theme, {
        name: 'Cost of deposits from SEC XBRL filings',
        min: 0,
        max: high,
        percent: true,
      }),
      yAxis: valueY(theme, {
        name: 'Cost of deposits from Call Reports',
        min: 0,
        max: high,
        gap: 44,
        percent: true,
      }),
      series: [
        diagonal(theme, 0, high),
        {
          type: 'scatter',
          symbolSize: 7,
          itemStyle: { color: theme.blue, opacity: 0.45 },
          data: pairs.map((p) => [p.filed, p.regulatory]),
        },
      ],
    },
  };
}
