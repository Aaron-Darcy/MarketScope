import type { EChartsOption } from 'echarts';

import type { Bank, Cycle, CycleName } from '../data/model';
import type { ChartTheme } from './theme';

export interface Built {
  readonly option: EChartsOption;
  /** The bank behind a clicked mark, where a mark stands for one. */
  readonly bankAt?: (seriesIndex: number, dataIndex: number) => Bank | undefined;
}

export function niceBounds(values: readonly number[], step = 0.1): [number, number] {
  const low = Math.min(...values);
  const high = Math.max(...values);
  return [Math.floor(low / step) * step, Math.ceil(high / step) * step];
}

/** Quarter categories labelled once a year, at the first quarter. */
export function quarterAxis(theme: ChartTheme, quarters: readonly string[]) {
  return {
    type: 'category' as const,
    data: [...quarters],
    boundaryGap: false,
    axisLine: { lineStyle: { color: theme.axis } },
    axisTick: { show: false },
    axisLabel: {
      color: theme.muted,
      interval: (_index: number, value: string) => value.endsWith('-03-31'),
      formatter: (value: string) => value.slice(0, 4),
    },
  };
}

/** The two tightening cycles shaded behind a quarterly series. */
export function cycleAreas(theme: ChartTheme, cycles: Readonly<Record<CycleName, Cycle>>) {
  return {
    silent: true,
    itemStyle: { color: theme.mode === 'light' ? 'rgba(235,104,52,0.07)' : 'rgba(217,89,38,0.12)' },
    label: { color: theme.secondary, fontSize: 11, position: 'insideTop' as const, distance: 8 },
    data: (['calibration', 'test'] as const).map((name) => [
      { name: `${cycles[name].years} cycle`, xAxis: cycles[name].start },
      { xAxis: cycles[name].end },
    ]) as [{ name: string; xAxis: string }, { xAxis: string }][],
  };
}
