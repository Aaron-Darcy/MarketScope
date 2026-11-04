import { useMemo, useState } from 'react';
import { Link } from 'react-router';

import { useSite } from '../app/site';
import { useChartTheme } from '../app/theme';
import {
  dumbbellChart,
  slopeChart,
  transitionHeatmap,
  type DumbbellRow,
} from '../charts/comparison';
import { DataTable, type Column } from '../components/DataTable';
import { Icon } from '../components/Icon';
import {
  ChartCard,
  PageHeader,
  Section,
  Segmented,
  Stat,
  useDocumentTitle,
} from '../components/ui';
import { fixed, longDate, pValue, signed } from '../data/format';
import {
  headlineSample,
  inSample,
  persistenceSummary,
  quartileTransitions,
  type Bank,
  type Membership,
} from '../data/model';

const tier = (value: string | null) => (value === null ? '–' : value);

const COLUMNS: readonly Column<Bank>[] = [
  {
    key: 'name',
    title: 'Bank',
    render: (b) => <Link to={`/banks/${String(b.cik)}`}>{b.name}</Link>,
    sortValue: (b) => b.name,
  },
  {
    key: 'calibration',
    title: '2015–19 beta',
    align: 'right',
    render: (b) => fixed(b.comparison.calibration_beta, 3),
    sortValue: (b) => b.comparison.calibration_beta,
  },
  {
    key: 'calibration_tier',
    title: 'Tier',
    align: 'center',
    render: (b) => tier(b.comparison.calibration_tier),
    sortValue: (b) => b.comparison.calibration_tier,
  },
  {
    key: 'test',
    title: '2022–23 beta',
    align: 'right',
    render: (b) => fixed(b.comparison.test_beta, 3),
    sortValue: (b) => b.comparison.test_beta,
  },
  {
    key: 'test_tier',
    title: 'Tier',
    align: 'center',
    render: (b) => tier(b.comparison.test_tier),
    sortValue: (b) => b.comparison.test_tier,
  },
  {
    key: 'shift',
    title: 'Quartile shift',
    align: 'center',
    render: (b) =>
      b.comparison.quartile_shift === null ? '–' : String(b.comparison.quartile_shift),
    sortValue: (b) =>
      b.comparison.quartile_shift === null ? null : Math.abs(b.comparison.quartile_shift),
  },
];

export function Comparison() {
  useDocumentTitle('Cross-bank comparison');
  const site = useSite();
  const theme = useChartTheme();
  const [selected, setSelected] = useState<number | null>(null);
  const [sample, setSample] = useState<Membership>('headline');

  const ranked = useMemo(() => headlineSample(site), [site]);
  const summary = useMemo(() => persistenceSummary(ranked), [ranked]);
  const slope = useMemo(() => slopeChart(ranked, theme, selected), [ranked, theme, selected]);
  const heat = useMemo(
    () => transitionHeatmap(quartileTransitions(ranked), theme),
    [ranked, theme],
  );

  const rows = useMemo((): DumbbellRow[] => {
    const filed = site.banks.flatMap((bank): DumbbellRow[] => {
      const c = bank.comparison;
      if (c.calibration_beta === null || c.test_beta === null) return [];
      return [
        {
          name: bank.name,
          calibrationBeta: c.calibration_beta,
          testBeta: c.test_beta,
          inHeadline: c.in_headline,
          note: c.in_headline ? undefined : 'Outside the headline sample',
          bank,
        },
      ];
    });
    const recovered = site.recovered.map((r): DumbbellRow => ({
      name: `${r.bank} (failed)`,
      calibrationBeta: r.calibration_beta,
      testBeta: r.test_beta,
      inHeadline: false,
      note: `Failed; never filed with the SEC. Betas from its Call Reports, test cycle to ${longDate(r.test_end)}`,
    }));
    return [...filed, ...recovered].sort((a, b) => b.testBeta - a.testBeta);
  }, [site]);
  const dumbbell = useMemo(() => dumbbellChart(rows, theme, selected), [rows, theme, selected]);

  const members = useMemo(
    () => site.banks.filter((bank) => inSample(bank, sample)),
    [site, sample],
  );
  const result = site.results.find((r) => r.sample === sample);

  return (
    <>
      <PageHeader
        eyebrow="Cross-bank comparison"
        title="Who kept their place, and who moved"
        lede="Where each bank sits among its peers, cycle by cycle. The test is of the ordering, so what matters is whether a bank kept its rank, not whether its beta rose."
      >
        <div className="header-stats">
          <Stat tone="onDark" value={summary.banks} label="banks in the headline sample" />
          <Stat tone="onDark" value={summary.sameQuartile} label="kept exactly the same quartile" />
          <Stat tone="onDark" value={summary.movedTwo} label="moved two quartiles or more" />
          <Stat tone="onDark" value={signed(site.headline.spearman)} label="rank correlation" />
        </div>
      </PageHeader>

      <div className="container toolbar">
        <label className="select">
          <span>Highlight a bank</span>
          <select
            value={selected ?? ''}
            onChange={(e) => {
              setSelected(e.target.value === '' ? null : Number(e.target.value));
            }}
          >
            <option value="">None</option>
            {ranked
              .map((b) => b.bank)
              .sort((a, b) => a.name.localeCompare(b.name))
              .map((b) => (
                <option key={b.cik} value={b.cik}>
                  {b.name}
                </option>
              ))}
          </select>
        </label>
        {selected !== null && (
          <Link to={`/banks/${String(selected)}`} className="text-link">
            Open its page <Icon name="arrow" size={14} />
          </Link>
        )}
      </div>

      <Section
        eyebrow="Rankings"
        title="Rank in one cycle against rank in the next"
        intro={
          <p>
            Each line is one bank, from the slowest repricer at the bottom to the fastest at the
            top. A flat line kept its rank. <span className="key-inline key-blue" /> kept the same
            quartile, <span className="key-inline key-orange" /> moved two or more,{' '}
            <span className="key-inline key-grey" /> moved one. Hover a line to isolate it.
          </p>
        }
      >
        <ChartCard
          built={slope}
          height={Math.max(480, ranked.length * 28)}
          label="Slope chart of each headline bank's rank in 2015–2019 and 2022–2023"
        />
      </Section>

      <Section
        tint
        eyebrow="Levels"
        title="Every bank, both cycles"
        intro={
          <p>
            Each bank’s beta in the calibration cycle and the test cycle. Every bank moved right,
            because the second cycle was faster and larger; what persists is the order. Italic names
            are outside the headline sample, and two are failed banks recovered from their Call
            Reports.
          </p>
        }
      >
        <ChartCard
          built={dumbbell}
          height={rows.length * 19 + 100}
          label="Dumbbell chart of every bank's deposit beta in both cycles"
        />
      </Section>

      <Section
        eyebrow="Quartiles"
        title="Quartile transitions"
        intro={
          <p>
            Read along a row: where the banks of one 2015–2019 quartile ended up in 2022–2023. The
            diagonal kept its quartile; by chance alone about {(summary.banks / 4).toFixed(1)}{' '}
            would.
          </p>
        }
      >
        <div className="narrow">
          <ChartCard
            built={heat}
            height={360}
            label="Heatmap of the number of banks moving between each pair of quartiles"
          />
        </div>
      </Section>

      <Section
        tint
        eyebrow="Samples"
        title="Who enters which sample"
        intro={
          <p>
            The headline admits a ranked bank with a tier 1 beta in both cycles, tier 1 cost of
            deposits in at least 80 percent of each cycle’s quarters, no partial cycle and no
            material acquisition inside either cycle. Each variant turns one of those rules.
          </p>
        }
      >
        <div className="toolbar toolbar-flush">
          <Segmented
            label="Sample"
            value={sample}
            onChange={setSample}
            options={[
              ['headline', 'Headline'],
              ['R1', 'R1'],
              ['R2', 'R2'],
              ['R3', 'R3'],
              ['R4', 'R4'],
            ]}
          />
        </div>
        {result && (
          <div className="card sample-summary">
            <div>
              <div className="eyebrow">{result.label}</div>
              <p>{result.description.charAt(0).toUpperCase() + result.description.slice(1)}.</p>
            </div>
            <div className="sample-figures">
              <Stat value={result.filers} label="banks" />
              <Stat value={signed(result.spearman)} label="Spearman" />
              <Stat value={pValue(result.p_value)} label="one-sided p" />
            </div>
          </div>
        )}
        <DataTable
          rows={members}
          columns={COLUMNS}
          rowKey={(b) => b.cik}
          caption={`Banks in the ${sample} sample with their betas and tiers`}
        />
      </Section>
    </>
  );
}
