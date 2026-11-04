import type { HeatmapSeriesOption } from 'echarts';

import type { Bank, RankedBank } from '../data/model';
import { baseOption, tooltipBase, itemTooltip, legend, tooltipHtml, valueX } from './base';
import type { Built } from './shared';
import type { ChartTheme } from './theme';

export type Placement = 'held' | 'shifted' | 'moved';

export function placement(quartileShift: number): Placement {
  if (Math.abs(quartileShift) >= 2) return 'moved';
  return quartileShift === 0 ? 'held' : 'shifted';
}

function placementColour(theme: ChartTheme, kind: Placement): string {
  return { held: theme.blue, shifted: theme.grey, moved: theme.orange }[kind];
}

/** One line per bank from its rank in the first cycle to its rank in the second. */
export function slopeChart(
  sample: readonly RankedBank[],
  theme: ChartTheme,
  selected: number | null,
): Built {
  const n = sample.length;
  return {
    option: {
      ...baseOption(theme),
      grid: { left: 180, right: 180, top: 40, bottom: 16 },
      tooltip: {
        ...tooltipBase(theme),
        trigger: 'item',
        formatter: itemTooltip((s) => {
          const b = sample[s];
          return b
            ? tooltipHtml(b.bank.name, [
                {
                  label: `rank of ${String(n)}, 2015–19 (beta ${b.calibrationBeta.toFixed(3)})`,
                  value: String(b.calibrationRank),
                  color: theme.blue,
                },
                {
                  label: `rank of ${String(n)}, 2022–23 (beta ${b.testBeta.toFixed(3)})`,
                  value: String(b.testRank),
                  color: theme.orange,
                },
              ])
            : null;
        }),
      },
      xAxis: {
        type: 'category',
        data: ['2015–2019 cycle', '2022–2023 cycle'],
        boundaryGap: false,
        position: 'top',
        axisLabel: { color: theme.ink, fontSize: 13, fontWeight: 600 },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      yAxis: { type: 'value', min: 0.5, max: n + 0.5, show: false },
      series: sample.map((b) => {
        const kind = placement(b.quartileShift);
        const isSelected = selected === b.bank.cik;
        const faded = selected !== null && !isSelected;
        const colour = placementColour(theme, kind);
        const text = {
          color: faded ? theme.muted : kind === 'shifted' ? theme.secondary : theme.ink,
          fontSize: 11,
          fontWeight: isSelected ? ('bold' as const) : ('normal' as const),
        };
        return {
          name: b.bank.name,
          type: 'line' as const,
          data: [b.calibrationRank, b.testRank],
          symbol: 'circle',
          symbolSize: isSelected ? 11 : 8,
          cursor: 'pointer',
          lineStyle: {
            color: colour,
            width: isSelected ? 4 : kind === 'shifted' ? 1.5 : 2.5,
            opacity: faded ? 0.25 : 1,
          },
          itemStyle: {
            color: colour,
            opacity: faded ? 0.25 : 1,
            borderColor: theme.surface,
            borderWidth: 1.5,
          },
          emphasis: { focus: 'series' as const, lineStyle: { width: 4 } },
          z: isSelected ? 3 : kind === 'shifted' ? 1 : 2,
          label: {
            show: true,
            position: 'left' as const,
            formatter: ({ dataIndex }: { dataIndex: number }) =>
              dataIndex === 0 ? b.bank.name : '',
            ...text,
          },
          endLabel: { show: true, formatter: b.bank.name, ...text },
        };
      }),
    },
    bankAt: (s) => sample[s]?.bank,
  };
}

export interface DumbbellRow {
  readonly name: string;
  readonly calibrationBeta: number;
  readonly testBeta: number;
  readonly inHeadline: boolean;
  readonly note?: string;
  readonly bank?: Bank;
}

/** Both cycles' betas for every bank that has them, fastest test-cycle repricer first. */
export function dumbbellChart(
  rows: readonly DumbbellRow[],
  theme: ChartTheme,
  selected: number | null,
): Built {
  const isSelected = (row: DumbbellRow) => selected !== null && row.bank?.cik === selected;
  return {
    option: {
      ...baseOption(theme),
      grid: { left: 210, right: 32, top: 36, bottom: 48 },
      legend: { ...legend(theme, ['2015–2019 beta', '2022–2023 beta']), top: 0, bottom: undefined },
      tooltip: {
        ...tooltipBase(theme),
        trigger: 'item',
        formatter: itemTooltip((_s, i) => {
          const r = rows[i];
          return r
            ? tooltipHtml(
                r.name,
                [
                  { label: '2015–19 beta', value: r.calibrationBeta.toFixed(3), color: theme.blue },
                  { label: '2022–23 beta', value: r.testBeta.toFixed(3), color: theme.orange },
                ],
                r.note,
              )
            : null;
        }),
      },
      xAxis: valueX(theme, {
        name: 'Deposit beta: the share of the policy rate rise passed on to depositors',
        min: 0,
        max: 1,
        gap: 28,
      }),
      yAxis: {
        type: 'category',
        inverse: true,
        data: rows.map((r) => r.name),
        axisTick: { show: false },
        axisLine: { show: false },
        axisLabel: {
          fontSize: 11,
          formatter: (value: string, index: number) => {
            const row = rows[index];
            if (!row) return value;
            if (isSelected(row)) return `{selected|${value}}`;
            return row.inHeadline ? `{in|${value}}` : `{out|${value}}`;
          },
          rich: {
            in: { color: theme.ink, fontSize: 11 },
            out: { color: theme.muted, fontSize: 11, fontStyle: 'italic' },
            selected: { color: theme.ink, fontSize: 12, fontWeight: 'bold' },
          },
        },
      },
      series: [
        {
          type: 'custom',
          silent: true,
          renderItem: (params, api) => {
            const index = params.dataIndex;
            const from = api.coord([api.value(0), index]);
            const to = api.coord([api.value(1), index]);
            const row = rows[index];
            return {
              type: 'line',
              shape: { x1: from[0], y1: from[1], x2: to[0], y2: to[1] },
              style: { stroke: row && isSelected(row) ? theme.ink : theme.grey, lineWidth: 2 },
            };
          },
          encode: { x: [0, 1], y: 2 },
          data: rows.map((r, i) => [r.calibrationBeta, r.testBeta, i]),
          z: 1,
        },
        {
          name: '2015–2019 beta',
          type: 'scatter',
          symbolSize: 11,
          cursor: 'pointer',
          itemStyle: { color: theme.blue, borderColor: theme.surface, borderWidth: 2 },
          data: rows.map((r, i) => [r.calibrationBeta, i]),
          z: 2,
        },
        {
          name: '2022–2023 beta',
          type: 'scatter',
          symbolSize: 11,
          cursor: 'pointer',
          itemStyle: { color: theme.orange, borderColor: theme.surface, borderWidth: 2 },
          data: rows.map((r, i) => [r.testBeta, i]),
          z: 2,
        },
      ],
    },
    bankAt: (_s, i) => rows[i]?.bank,
  };
}

const QUARTILES = ['Slowest quarter', 'Q2', 'Q3', 'Fastest quarter'];

/** Banks per pair of quartiles; the diagonal kept its quartile, which chance gives a quarter. */
export function transitionHeatmap(grid: readonly (readonly number[])[], theme: ChartTheme): Built {
  const max = Math.max(...grid.flat());
  const cells = grid.flatMap((row, from) =>
    row.map((banks, to) => ({
      value: [to, from, banks],
      label: { color: banks > max / 2 ? '#ffffff' : theme.ink },
    })),
  );
  return {
    option: {
      ...baseOption(theme),
      grid: { left: 140, right: 24, top: 40, bottom: 24 },
      tooltip: {
        ...tooltipBase(theme),
        trigger: 'item',
        formatter: itemTooltip((_s, i) => {
          const from = Math.floor(i / 4);
          const to = i % 4;
          const banks = grid[from]?.[to];
          return banks === undefined
            ? null
            : tooltipHtml(`${QUARTILES[from] ?? ''} → ${QUARTILES[to] ?? ''}`, [
                { label: banks === 1 ? 'bank' : 'banks', value: String(banks) },
              ]);
        }),
      },
      xAxis: {
        type: 'category',
        position: 'top',
        name: '2022–2023 quartile',
        nameLocation: 'middle',
        nameGap: 28,
        nameTextStyle: { color: theme.secondary },
        data: QUARTILES,
        axisLabel: { color: theme.secondary },
        axisLine: { show: false },
        axisTick: { show: false },
        splitArea: { show: false },
      },
      yAxis: {
        type: 'category',
        inverse: true,
        name: '2015–2019 quartile',
        nameLocation: 'middle',
        nameGap: 116,
        nameRotate: 90,
        nameTextStyle: { color: theme.secondary },
        data: QUARTILES,
        axisLabel: { color: theme.secondary },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      visualMap: {
        show: false,
        min: 0,
        max,
        inRange: { color: [...theme.sequential] },
      },
      series: [
        {
          type: 'heatmap',
          data: cells,
          label: { show: true, fontSize: 16, fontWeight: 600 },
          itemStyle: { borderColor: theme.surface, borderWidth: 3, borderRadius: 6 },
          emphasis: { itemStyle: { borderColor: theme.ink, borderWidth: 2 } },
        } satisfies HeatmapSeriesOption,
      ],
    },
  };
}
