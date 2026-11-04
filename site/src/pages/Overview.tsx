import { useMemo } from 'react';
import { Link } from 'react-router';

import { useSite } from '../app/site';
import { useChartTheme } from '../app/theme';
import { crossCycleScatter, forestPlot, ratePath } from '../charts/persistence';
import { Icon } from '../components/Icon';
import { METHODOLOGY } from '../components/links';
import { ChartCard, CountUp, Section, Stat, useDocumentTitle } from '../components/ui';
import { basisPoints, count, percent, pValue, quarterLabel, signed } from '../data/format';
import {
  coverageSummary,
  headlineSample,
  persistenceSummary,
  validationSummary,
} from '../data/model';

export function Overview() {
  useDocumentTitle('');
  const site = useSite();
  const theme = useChartTheme();
  const { headline, cycles } = site;

  const sample = useMemo(() => headlineSample(site), [site]);
  const summary = useMemo(() => persistenceSummary(sample), [sample]);
  const validation = useMemo(() => validationSummary(site.quarters), [site]);
  const coverage = useMemo(() => coverageSummary(site), [site]);
  const scatter = useMemo(() => crossCycleScatter(sample, theme), [sample, theme]);
  const forest = useMemo(() => forestPlot(site.results, theme), [site, theme]);
  const rates = useMemo(() => ratePath(site.policy, cycles, theme), [site, cycles, theme]);
  const moved = sample.filter((b) => b.materialDeviator).map((b) => b.bank.name);

  return (
    <>
      <section className="hero">
        <div className="container hero-grid">
          <div className="hero-copy">
            <div className="eyebrow eyebrow-light">
              US bank deposit pricing · two tightening cycles
            </div>
            <h1>Do banks reprice deposits the same way twice?</h1>
            <p className="hero-lede">
              When the Federal Reserve raises rates, each bank decides how much of the rise to pass
              on to its depositors. That share is its <strong>deposit beta</strong>. MarketScope
              measures it for the largest US banks, straight from their SEC filings, and asks
              whether the fastest repricers of 2015–2019 were the fastest again in 2022–2023.
            </p>
            <div className="hero-actions">
              <Link to="/banks" className="button button-primary">
                Explore the banks <Icon name="arrow" />
              </Link>
              <Link to="/persistence" className="button button-ghost">
                Read the case study
              </Link>
            </div>
          </div>
          <div className="hero-figure">
            <div className="hero-figure-label">Headline result</div>
            <div className="hero-number">
              <CountUp value={headline.spearman} format={(v) => signed(v, 2)} />
            </div>
            <p>
              rank correlation between each bank’s deposit beta in the two cycles, across{' '}
              {headline.filers} banks
            </p>
            <div className={headline.supported ? 'verdict verdict-yes' : 'verdict verdict-no'}>
              <Icon name={headline.supported ? 'check' : 'cross'} size={16} />
              {headline.supported
                ? `Persistence supported · p ${pValue(headline.p_value)}`
                : `Persistence not shown · p ${pValue(headline.p_value)}`}
            </div>
          </div>
        </div>
      </section>

      <div className="container stat-strip">
        <Stat
          value={`${String(summary.stayedFastest)} of 6`}
          label="fastest repricers stayed among the six fastest"
        />
        <Stat
          value={summary.sameQuartile}
          label={`of ${String(summary.banks)} banks sat in the same quartile both times`}
        />
        <Stat
          value={basisPoints(validation.medianGapBp)}
          label="median gap to the banks’ own Call Reports"
        />
        <Stat
          value={count(coverage.costQuarters)}
          label={`bank-quarters across ${String(coverage.banks)} filers`}
        />
      </div>

      <Section
        eyebrow="The finding"
        title={headline.supported ? 'Fast repricers stayed fast' : 'Persistence is not shown'}
        intro={
          <p>
            Across {headline.filers} banks the ordering by deposit beta in 2015–2019 carries into
            2022–2023 with a rank correlation of {signed(headline.spearman)}, on a test fixed before
            the result was computed. {summary.sameQuartile} banks sat in the same quartile both
            times, where chance alone would put about {(summary.banks / 4).toFixed(1)}.
          </p>
        }
      >
        <div className="split">
          <ChartCard
            title="Deposit beta, cycle against cycle"
            subtitle="Each dot is a bank. Select one to open its page."
            built={scatter}
            height={460}
            label={`Scatter of ${String(sample.length)} banks' deposit betas in 2015–2019 against 2022–2023`}
          />
          <aside className="callouts">
            <div className="callout">
              <h3>Why every dot sits above the line</h3>
              <p>
                The second cycle was faster and larger, so every bank passed on more of it. The
                claim is about order, not level: banks further right sit higher.
              </p>
            </div>
            <div className="callout callout-accent">
              <h3>The banks that moved</h3>
              <p>
                {moved.join(', ')} moved two quartiles or more. The case study gives a hypothesis
                for each, and says which have been tested.
              </p>
              <Link to="/persistence#movers" className="text-link">
                See the explanations <Icon name="arrow" size={14} />
              </Link>
            </div>
          </aside>
        </div>
      </Section>

      <Section
        tint
        eyebrow="Context"
        title="Two very different cycles"
        intro={
          <p>
            The first tightening took three years to move rates about two points. The second moved
            them more than five in under two. Betas rise in a cycle like that, which is why levels
            are not compared across them and the ordering is.
          </p>
        }
      >
        <div className="split split-wide">
          <ChartCard
            title="Federal funds rate, quarterly average"
            built={rates}
            height={300}
            label="Line chart of the federal funds rate since 2008 with the two cycles shaded"
          />
          <div className="cycle-cards">
            {(['calibration', 'test'] as const).map((name) => {
              const c = cycles[name];
              return (
                <div key={name} className="card cycle-card">
                  <div className="eyebrow">
                    {name === 'calibration' ? 'Calibration cycle' : 'Test cycle'}
                  </div>
                  <div className="cycle-years">{c.years}</div>
                  <div className="cycle-move">
                    {percent(c.startRate, 2)} <Icon name="arrow" size={16} />{' '}
                    {percent(c.endRate, 2)}
                  </div>
                  <div className="muted">
                    {quarterLabel(c.start)} to {quarterLabel(c.end)} · {c.months} months
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </Section>

      <Section
        eyebrow="Robustness"
        title="The result survives every check"
        intro={
          <p>
            Four variants of the sample were registered beside the headline before anything was
            computed. Each gives the same answer, and adding the failed banks an EDGAR-only study
            leaves out makes it stronger, not weaker.
          </p>
        }
      >
        <ChartCard
          built={forest}
          height={320}
          label="Forest plot of the rank correlation and its 95 percent interval for each registered sample"
        />
      </Section>

      <Section tint eyebrow="Scope" title="What is and is not claimed">
        <div className="claims">
          <div className="card claim claim-yes">
            <h3>
              <Icon name="check" /> Claimed
            </h3>
            <ul>
              <li>
                Across these banks, a bank’s place in the deposit beta ordering in one cycle is
                associated with its place in the next, on a test fixed in advance.
              </li>
              <li>
                The figures behind it match the banks’ own Call Reports: a median gap of{' '}
                {basisPoints(validation.medianGapBp)}, and {percent(validation.withinTenBp, 0)} of{' '}
                {count(validation.pairs)} bank-quarters within 10 bp.
              </li>
            </ul>
          </div>
          <div className="card claim claim-no">
            <h3>
              <Icon name="cross" /> Not claimed
            </h3>
            <ul>
              <li>
                A forecast for any one bank. The interval runs {signed(headline.interval_low)} to{' '}
                {signed(headline.interval_high)}.
              </li>
              <li>Anything about failure or distress.</li>
              <li>
                That beta levels carry over between cycles, or that deposit betas are a new idea.
              </li>
            </ul>
          </div>
        </div>
      </Section>

      <Section eyebrow="Explore" title="Go deeper">
        <div className="explore-grid">
          <Link to="/banks" className="card explore-card">
            <h3>Bank explorer</h3>
            <p>Every bank’s cost of deposits against the Fed, cycle by cycle.</p>
            <span className="text-link">
              {coverage.banks} banks <Icon name="arrow" size={14} />
            </span>
          </Link>
          <Link to="/comparison" className="card explore-card">
            <h3>Cross-bank comparison</h3>
            <p>Who moved, who held, and by how much.</p>
            <span className="text-link">
              Rankings and quartiles <Icon name="arrow" size={14} />
            </span>
          </Link>
          <Link to="/persistence" className="card explore-card">
            <h3>Persistence case study</h3>
            <p>The plan, the test, the checks and what it does not show.</p>
            <span className="text-link">
              Read it <Icon name="arrow" size={14} />
            </span>
          </Link>
          <a href={METHODOLOGY} className="card explore-card">
            <h3>Methodology</h3>
            <p>How every figure is produced, and what is not yet handled.</p>
            <span className="text-link">
              On GitHub <Icon name="external" size={14} />
            </span>
          </a>
        </div>
      </Section>
    </>
  );
}
