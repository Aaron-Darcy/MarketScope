import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router';

import { Chart, type ChartClick } from '../charts/Chart';
import type { Built } from '../charts/shared';
import type { Status } from '../data/model';

export function useDocumentTitle(title: string) {
  useEffect(() => {
    document.title = title ? `${title} · MarketScope` : 'MarketScope';
  }, [title]);
}

interface PageHeaderProps {
  readonly eyebrow: string;
  readonly title: string;
  readonly lede?: ReactNode;
  readonly children?: ReactNode;
}

export function PageHeader({ eyebrow, title, lede, children }: PageHeaderProps) {
  return (
    <section className="page-header">
      <div className="container">
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        {lede && <p className="lede">{lede}</p>}
        {children}
      </div>
    </section>
  );
}

interface StatProps {
  readonly value: ReactNode;
  readonly label: ReactNode;
  readonly tone?: 'plain' | 'onDark';
}

export function Stat({ value, label, tone = 'plain' }: StatProps) {
  return (
    <div className={tone === 'onDark' ? 'stat stat-dark' : 'stat'}>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

interface SectionProps {
  readonly id?: string;
  readonly eyebrow?: string;
  readonly title: string;
  readonly intro?: ReactNode;
  readonly children: ReactNode;
  readonly tint?: boolean;
}

export function Section({ id, eyebrow, title, intro, children, tint = false }: SectionProps) {
  return (
    <section id={id} className={tint ? 'section section-tint' : 'section'}>
      <div className="container">
        <div className="section-head">
          {eyebrow && <div className="eyebrow">{eyebrow}</div>}
          <h2>{title}</h2>
          {intro && <div className="section-intro">{intro}</div>}
        </div>
        {children}
      </div>
    </section>
  );
}

interface ChartCardProps {
  readonly title?: string;
  readonly subtitle?: ReactNode;
  readonly built: Built;
  readonly height: number;
  readonly label: string;
  readonly footer?: ReactNode;
}

/** A chart in a card; a click on a mark that stands for a bank opens that bank's page. */
export function ChartCard({ title, subtitle, built, height, label, footer }: ChartCardProps) {
  const navigate = useNavigate();
  const { bankAt } = built;
  const onClick = useCallback(
    ({ seriesIndex, dataIndex }: ChartClick) => {
      const bank = bankAt?.(seriesIndex, dataIndex);
      if (bank) void navigate(`/banks/${String(bank.cik)}`);
    },
    [bankAt, navigate],
  );
  return (
    <figure className="card chart-card">
      {(title ?? subtitle) && (
        <figcaption className="card-head">
          {title && <h3>{title}</h3>}
          {subtitle && <p>{subtitle}</p>}
        </figcaption>
      )}
      <Chart
        option={built.option}
        height={height}
        label={label}
        onClick={bankAt ? onClick : undefined}
      />
      {footer && <div className="card-foot">{footer}</div>}
    </figure>
  );
}

const STATUS_TEXT: Readonly<Record<Status, string>> = {
  filing: 'Filing',
  merged: 'Merged',
  failed: 'Failed',
  deregistered: 'Deregistered',
};

export function StatusPill({
  status,
  year,
}: {
  readonly status: Status;
  readonly year?: string | null;
}) {
  return (
    <span className={`pill pill-${status}`}>
      {STATUS_TEXT[status]}
      {year ? ` ${year}` : ''}
    </span>
  );
}

interface SegmentedProps<T extends string> {
  readonly label: string;
  readonly value: T;
  readonly options: readonly (readonly [T, string])[];
  readonly onChange: (value: T) => void;
}

export function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
}: SegmentedProps<T>) {
  return (
    <div className="segmented" role="radiogroup" aria-label={label}>
      {options.map(([key, text]) => (
        <button
          key={key}
          type="button"
          role="radio"
          aria-checked={value === key}
          className={value === key ? 'active' : ''}
          onClick={() => {
            onChange(key);
          }}
        >
          {text}
        </button>
      ))}
    </div>
  );
}

function prefersReducedMotion(): boolean {
  return matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/** A figure that counts up to its value once, unless the reader has asked for less motion. */
export function CountUp({
  value,
  format,
  duration = 1200,
}: {
  readonly value: number;
  readonly format: (value: number) => string;
  readonly duration?: number;
}) {
  const [shown, setShown] = useState(() => (prefersReducedMotion() ? value : 0));
  useEffect(() => {
    if (prefersReducedMotion()) return;
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      setShown(value * (1 - (1 - t) ** 3));
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(frame);
    };
  }, [value, duration]);
  return <span aria-label={format(value)}>{format(shown)}</span>;
}

/** A thin bar for a share between 0 and 1. */
export function Meter({ share, label }: { readonly share: number; readonly label: string }) {
  return (
    <div
      className="meter"
      role="meter"
      aria-valuemin={0}
      aria-valuemax={1}
      aria-valuenow={share}
      aria-label={label}
    >
      <div className="meter-fill" style={{ width: `${(share * 100).toFixed(1)}%` }} />
    </div>
  );
}
