import { useDeferredValue, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router';

import { useSite } from '../app/site';
import { useChartTheme } from '../app/theme';
import { coverageBars } from '../charts/bank';
import { DataTable, type Column } from '../components/DataTable';
import { Icon } from '../components/Icon';
import { sparkPath } from '../components/sparkline';
import {
  ChartCard,
  Meter,
  PageHeader,
  Section,
  Segmented,
  Stat,
  StatusPill,
  useDocumentTitle,
} from '../components/ui';
import { basisPoints, count, fixed, percent } from '../data/format';
import { coverageSummary, type Bank, type PolicyPoint } from '../data/model';

type StatusFilter = 'all' | 'filing' | 'exited';
type SortKey = 'rank' | 'name' | 'test' | 'calibration' | 'tier1';
type View = 'cards' | 'table';

const SORTS: Readonly<Record<SortKey, (a: Bank, b: Bank) => number>> = {
  rank: (a, b) => (a.rank ?? Infinity) - (b.rank ?? Infinity),
  name: (a, b) => a.name.localeCompare(b.name),
  test: (a, b) => (b.overview.test_beta ?? -1) - (a.overview.test_beta ?? -1),
  calibration: (a, b) => (b.overview.calibration_beta ?? -1) - (a.overview.calibration_beta ?? -1),
  tier1: (a, b) => b.overview.tier_1_share - a.overview.tier_1_share,
};

const SPARK_WIDTH = 240;
const SPARK_HEIGHT = 56;

function Sparkline({
  bank,
  policy,
}: {
  readonly bank: Bank;
  readonly policy: readonly PolicyPoint[];
}) {
  const quarters = policy.map((p) => p.quarter);
  const own = new Map(bank.quarters.map((q) => [q.quarter_end, q.cost_of_deposits]));
  const costs = quarters.map((q) => own.get(q) ?? null);
  const rates = policy.map((p) => p.rate);
  const top = Math.max(0.01, ...rates, ...costs.filter((c): c is number => c !== null));
  const domain = [0, top] as const;
  return (
    <svg
      className="spark"
      viewBox={`0 0 ${String(SPARK_WIDTH)} ${String(SPARK_HEIGHT)}`}
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path className="spark-rate" d={sparkPath(rates, SPARK_WIDTH, SPARK_HEIGHT, domain)} />
      <path className="spark-cost" d={sparkPath(costs, SPARK_WIDTH, SPARK_HEIGHT, domain)} />
    </svg>
  );
}

function exitYear(bank: Bank): string | null {
  return bank.exitDate ? bank.exitDate.slice(0, 4) : null;
}

function BankCard({
  bank,
  policy,
}: {
  readonly bank: Bank;
  readonly policy: readonly PolicyPoint[];
}) {
  const o = bank.overview;
  return (
    <Link to={`/banks/${String(bank.cik)}`} className="card bank-card">
      <div className="bank-card-top">
        <span className="rank-badge">{bank.rank ?? '–'}</span>
        <StatusPill status={bank.status} year={exitYear(bank)} />
      </div>
      <h3>{bank.name}</h3>
      <Sparkline bank={bank} policy={policy} />
      <div className="bank-card-betas">
        <div>
          <span className="beta-value">{fixed(o.calibration_beta)}</span>
          <span className="beta-label">2015–19 beta</span>
        </div>
        <div>
          <span className="beta-value">{fixed(o.test_beta)}</span>
          <span className="beta-label">2022–23 beta</span>
        </div>
      </div>
      <div className="bank-card-meter">
        <Meter
          share={o.tier_1_share}
          label={`${percent(o.tier_1_share, 0)} of quarters at tier 1`}
        />
        <span>{percent(o.tier_1_share, 0)} at tier 1</span>
      </div>
    </Link>
  );
}

const COLUMNS: readonly Column<Bank>[] = [
  {
    key: 'rank',
    title: 'Rank',
    align: 'center',
    render: (b) => b.rank ?? '–',
    sortValue: (b) => b.rank,
  },
  {
    key: 'name',
    title: 'Bank',
    render: (b) => <Link to={`/banks/${String(b.cik)}`}>{b.name}</Link>,
    sortValue: (b) => b.name,
  },
  {
    key: 'status',
    title: 'Status',
    render: (b) => <StatusPill status={b.status} year={exitYear(b)} />,
    sortValue: (b) => b.status,
  },
  {
    key: 'quarters',
    title: 'Quarters',
    align: 'right',
    render: (b) => b.overview.cost_quarters,
    sortValue: (b) => b.overview.cost_quarters,
  },
  {
    key: 'tier1',
    title: 'At tier 1',
    align: 'right',
    render: (b) => percent(b.overview.tier_1_share, 0),
    sortValue: (b) => b.overview.tier_1_share,
  },
  {
    key: 'calibration',
    title: '2015–19 beta',
    align: 'right',
    render: (b) => fixed(b.overview.calibration_beta, 3),
    sortValue: (b) => b.overview.calibration_beta,
  },
  {
    key: 'test',
    title: '2022–23 beta',
    align: 'right',
    render: (b) => fixed(b.overview.test_beta, 3),
    sortValue: (b) => b.overview.test_beta,
  },
  {
    key: 'gap',
    title: 'Gap to Call Reports',
    align: 'right',
    render: (b) => basisPoints(b.overview.median_regulatory_gap_bp),
    sortValue: (b) => b.overview.median_regulatory_gap_bp,
  },
];

export function Banks() {
  useDocumentTitle('Bank explorer');
  const site = useSite();
  const theme = useChartTheme();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState<StatusFilter>('all');
  const [sort, setSort] = useState<SortKey>('rank');
  const [view, setView] = useState<View>('cards');
  const search = useDeferredValue(query.trim().toLowerCase());

  const coverage = useMemo(() => coverageSummary(site), [site]);
  const shown = useMemo(
    () =>
      site.banks
        .filter((b) => status === 'all' || (status === 'filing') === (b.status === 'filing'))
        .filter((b) => search === '' || b.name.toLowerCase().includes(search))
        .sort(SORTS[sort]),
    [site, status, search, sort],
  );
  const bars = useMemo(() => coverageBars(shown, theme), [shown, theme]);

  return (
    <>
      <PageHeader
        eyebrow="Bank explorer"
        title={`${String(coverage.banks)} banks, every quarter they filed`}
        lede="The largest fifty US deposit-taking banks by peak total assets across 2015–2023, and one terminal filer pinned beside them. Banks that have since merged, deregistered or failed are kept, so the sample is not survivors only."
      >
        <div className="header-stats">
          <Stat tone="onDark" value={coverage.banks} label="banks" />
          <Stat
            tone="onDark"
            value={count(coverage.costQuarters)}
            label="bank-quarters with a cost of deposits"
          />
          <Stat
            tone="onDark"
            value={percent(coverage.tier1Share, 0)}
            label="of them at tier 1, the most precise"
          />
          <Stat tone="onDark" value={coverage.exited} label="merged, deregistered or failed" />
        </div>
      </PageHeader>

      <div className="container toolbar" role="search">
        <label className="search">
          <Icon name="search" />
          <input
            type="search"
            placeholder="Search banks"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
            }}
            aria-label="Search banks by name"
          />
        </label>
        <Segmented
          label="Filing status"
          value={status}
          onChange={setStatus}
          options={[
            ['all', 'All'],
            ['filing', 'Still filing'],
            ['exited', 'Exited'],
          ]}
        />
        <label className="select">
          <span>Sort</span>
          <select
            value={sort}
            onChange={(e) => {
              setSort(e.target.value as SortKey);
            }}
          >
            <option value="rank">Rank by assets</option>
            <option value="name">Name</option>
            <option value="test">2022–23 beta, highest first</option>
            <option value="calibration">2015–19 beta, highest first</option>
            <option value="tier1">Share at tier 1</option>
          </select>
        </label>
        <Segmented
          label="View"
          value={view}
          onChange={setView}
          options={[
            ['cards', 'Cards'],
            ['table', 'Table'],
          ]}
        />
        <span className="toolbar-count">
          {shown.length} of {site.banks.length}
        </span>
      </div>

      <div className="container">
        {shown.length === 0 ? (
          <p className="empty">No bank matches “{query}”.</p>
        ) : view === 'cards' ? (
          <>
            <div className="legend-row" aria-hidden="true">
              <span className="key key-cost" /> Cost of deposits
              <span className="key key-rate" /> Federal funds rate
            </div>
            <div className="bank-grid">
              {shown.map((bank) => (
                <BankCard key={bank.cik} bank={bank} policy={site.policy} />
              ))}
            </div>
          </>
        ) : (
          <DataTable
            rows={shown}
            columns={COLUMNS}
            rowKey={(b) => b.cik}
            caption="Every bank in the universe with its betas, tier coverage and gap to its Call Reports"
            onRowClick={(b) => void navigate(`/banks/${String(b.cik)}`)}
          />
        )}
      </div>

      <Section
        eyebrow="Coverage"
        title="How much of each bank’s history resolves"
        intro={
          <p>
            Every bank-quarter carries a comparability tier, from tier 1, the most precise, to tier
            X, a reconstruction that failed its completeness check. The chart follows the filters
            above.
          </p>
        }
      >
        <ChartCard
          built={bars}
          height={Math.max(160, shown.length * 19 + 80)}
          label="Stacked bars of each bank's quarters by comparability tier"
        />
      </Section>
    </>
  );
}
