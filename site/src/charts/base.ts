import type {
  EChartsOption,
  TooltipComponentOption,
  TooltipComponentFormatterCallbackParams,
  XAXisComponentOption,
  YAXisComponentOption,
} from 'echarts';

import { FONT, type ChartTheme } from './theme';

type Params = Exclude<TooltipComponentFormatterCallbackParams, unknown[]>;

const ENTITIES: Readonly<Record<string, string>> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
};

/** ECharts renders tooltips as HTML, so every label from the data is escaped first. */
export function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (c) => ENTITIES[c] ?? c);
}

export interface TooltipRow {
  readonly label: string;
  readonly value: string;
  readonly color?: string;
}

/** Value first, label second: the reader already knows the series and wants the number. */
export function tooltipHtml(title: string, rows: readonly TooltipRow[], note?: string): string {
  const body = rows
    .map(
      (row) =>
        `<div class="tt-row">${
          row.color ? `<span class="tt-key" style="background:${row.color}"></span>` : ''
        }<b>${escapeHtml(row.value)}</b><span>${escapeHtml(row.label)}</span></div>`,
    )
    .join('');
  const footer = note ? `<div class="tt-note">${escapeHtml(note)}</div>` : '';
  return `<div class="tt"><div class="tt-title">${escapeHtml(title)}</div>${body}${footer}</div>`;
}

/** A per-mark tooltip that looks its row up by series and index rather than trusting `data`. */
export function itemTooltip(
  format: (seriesIndex: number, dataIndex: number) => string | null,
): (params: TooltipComponentFormatterCallbackParams) => string {
  return (params) => {
    const item: Params | undefined = Array.isArray(params) ? params[0] : params;
    if (!item) return '';
    return format(item.seriesIndex ?? 0, item.dataIndex) ?? '';
  };
}

export function tooltipBase(theme: ChartTheme): TooltipComponentOption {
  return {
    backgroundColor: theme.surface,
    borderColor: theme.grid,
    borderWidth: 1,
    padding: [10, 12],
    textStyle: { color: theme.ink, fontFamily: FONT, fontSize: 12 },
    extraCssText: 'border-radius:10px;box-shadow:0 8px 24px rgba(0,0,0,0.12);',
    confine: true,
  };
}

export function baseOption(theme: ChartTheme): EChartsOption {
  return {
    backgroundColor: 'transparent',
    textStyle: { fontFamily: FONT, color: theme.secondary },
    animationDuration: 700,
    animationEasing: 'cubicOut',
    tooltip: tooltipBase(theme),
  };
}

interface AxisOptions {
  readonly name?: string;
  readonly min?: number;
  readonly max?: number;
  readonly gap?: number;
  readonly percent?: boolean;
  readonly format?: (value: number) => string;
}

function axisCommon(theme: ChartTheme, options: AxisOptions) {
  return {
    type: 'value' as const,
    name: options.name,
    nameLocation: 'middle' as const,
    nameGap: options.gap ?? 32,
    nameTextStyle: { color: theme.secondary, fontSize: 12 },
    min: options.min,
    max: options.max,
    axisLabel: {
      color: theme.muted,
      formatter: options.percent ? (v: number) => `${(v * 100).toFixed(0)}%` : options.format,
    },
    axisLine: { show: false },
    axisTick: { show: false },
    splitLine: { lineStyle: { color: theme.grid } },
  };
}

export function valueX(theme: ChartTheme, options: AxisOptions = {}): XAXisComponentOption {
  return axisCommon(theme, options);
}

export function valueY(theme: ChartTheme, options: AxisOptions = {}): YAXisComponentOption {
  return axisCommon(theme, options);
}

/** The x = y line, which a bank on it kept its value or rank exactly. */
export function diagonal(theme: ChartTheme, low: number, high: number) {
  return {
    name: 'Equal in both cycles',
    type: 'line' as const,
    data: [
      [low, low],
      [high, high],
    ],
    symbol: 'none',
    silent: true,
    lineStyle: { color: theme.axis, width: 1 },
    tooltip: { show: false },
    z: 1,
  };
}

export function legend(theme: ChartTheme, names: readonly string[]) {
  return {
    bottom: 0,
    icon: 'circle',
    itemWidth: 10,
    itemHeight: 10,
    textStyle: { color: theme.secondary, fontSize: 12 },
    data: [...names],
  };
}
