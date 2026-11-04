import type { EChartsOption } from 'echarts';
import { BarChart, CustomChart, HeatmapChart, LineChart, ScatterChart } from 'echarts/charts';
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  TooltipComponent,
  VisualMapComponent,
} from 'echarts/components';
import * as echarts from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { useEffect, useRef } from 'react';

// Only the chart types and components the pages draw are registered, so the rest of
// ECharts stays out of the bundle.
echarts.use([
  BarChart,
  CustomChart,
  HeatmapChart,
  LineChart,
  ScatterChart,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  TooltipComponent,
  VisualMapComponent,
  CanvasRenderer,
]);

export interface ChartClick {
  readonly seriesIndex: number;
  readonly dataIndex: number;
}

interface ChartProps {
  readonly option: EChartsOption;
  readonly height: number;
  /** Read by screen readers in place of the canvas. */
  readonly label: string;
  readonly onClick?: (click: ChartClick) => void;
}

export function Chart({ option, height, label, onClick }: ChartProps) {
  const container = useRef<HTMLDivElement>(null);
  const instance = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    const element = container.current;
    if (!element) return;
    const chart = echarts.init(element, null, { renderer: 'canvas' });
    instance.current = chart;
    const observer = new ResizeObserver(() => {
      chart.resize();
    });
    observer.observe(element);
    return () => {
      observer.disconnect();
      chart.dispose();
      instance.current = null;
    };
  }, []);

  useEffect(() => {
    instance.current?.setOption(option, { notMerge: true });
  }, [option]);

  useEffect(() => {
    const chart = instance.current;
    if (!chart || !onClick) return;
    const handler = (params: { seriesIndex?: number; dataIndex?: number }) => {
      if (params.seriesIndex !== undefined && params.dataIndex !== undefined) {
        onClick({ seriesIndex: params.seriesIndex, dataIndex: params.dataIndex });
      }
    };
    chart.on('click', handler);
    return () => {
      chart.off('click', handler);
    };
  }, [onClick]);

  return <div ref={container} className="chart" style={{ height }} role="img" aria-label={label} />;
}
