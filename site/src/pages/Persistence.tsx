import { useMemo } from 'react';
import { Link } from 'react-router';

import { useSite } from '../app/site';
import { useChartTheme } from '../app/theme';
import {
  forestPlot,
  rankScatter,
  ratePath,
  survivorshipScatter,
  validationScatter,
  type SurvivorPoint,
} from '../charts/persistence';
import { Icon } from '../components/Icon';
import { METHODOLOGY, REPOSITORY } from '../components/links';
import { ChartCard, PageHeader, Stat, useDocumentTitle } from '../components/ui';
import {
  basisPoints,
  count,
  fixed,
  longDate,
  percent,
  pValue,
  quarterLabel,
  signed,
} from '../data/format';
import { headlineSample, validationPairs, validationSummary } from '../data/model';
import { linearFit, median } from '../data/stats';

const CONTENTS = [
  ['cycles', 'Two cycles'],
  ['plan', 'The plan'],
  ['result', 'The result'],
  ['robustness', 'Robustness'],
  ['survivorship', 'Survivorship'],
  ['movers', 'Banks that moved'],
  ['validation', 'Banks or tagging?'],
  ['limits', 'What it does not show'],
] as const;

export function Persistence() {
  useDocumentTitle('Deposit beta persistence');
  const site = useSite();
  const theme = useChartTheme();
  const { headline, cycles } = site;
  const calibration = cycles.calibration;
  const test = cycles.test;

  const sample = useMemo(() => headlineSample(site), [site]);
  const fit = useMemo(
    () => linearFit(sample.map((b) => [b.calibrationBeta, b.testBeta])),
    [sample],
  );
  const pairs = useMemo(() => validationPairs(site.quarters), [site]);
  const validation = useMemo(() => validationSummary(site.quarters), [site]);
  const recoveredResult = site.results.find((r) => r.sample === 'R4+recovered');
  const movers = sample
    .filter((b) => b.materialDeviator)
    .sort((a, b) => b.quartileShift - a.quartileShift);

  const survivors = useMemo((): SurvivorPoint[] => {
    const filed = site.banks.flatMap((bank): SurvivorPoint[] => {
      const c = bank.comparison;
      if (!c.in_r4 || c.calibration_beta === null || c.test_beta === null) return [];
      const failed = bank.status === 'failed';
      return [
        {
          name: bank.name,
          calibrationBeta: c.calibration_beta,
          testBeta: c.test_beta,
          failed,
          note: failed
            ? `Test beta to its last filing, ${longDate(bank.lastFiledPeriod)}`
            : undefined,
          bank,
        },
      ];
    });
    const recovered = site.recovered.map((r) => ({
      name: r.bank,
      calibrationBeta: r.calibration_beta,
      testBeta: r.test_beta,
      failed: true,
      note: `From its Call Reports; test beta to ${longDate(r.test_end)}`,
    }));
    return [...filed, ...recovered];
  }, [site]);

  const rates = useMemo(() => ratePath(site.policy, cycles, theme), [site, cycles, theme]);
  const ranks = useMemo(() => rankScatter(sample, theme), [sample, theme]);
  const forest = useMemo(() => forestPlot(site.results, theme), [site, theme]);
  const survival = useMemo(() => survivorshipScatter(survivors, theme), [survivors, theme]);
  const checks = useMemo(
    () => validationScatter(pairs, (cik) => site.bankByCik.get(cik)?.name ?? String(cik), theme),
    [pairs, site, theme],
  );

  return (
    <>
      <PageHeader
        eyebrow="Case study"
        title="Deposit beta persistence"
        lede="Whether a bank’s deposit beta is a property of the bank: whether the banks that repriced fastest in one tightening cycle did so again in the next."
      />

      <div className="container article-layout">
        <nav className="toc" aria-label="On this page">
          <div className="eyebrow">On this page</div>
          {CONTENTS.map(([id, label]) => (
            <a key={id} href={`#${id}`}>
              {label}
            </a>
          ))}
        </nav>

        <article className="article">
          <p className="article-lede">
            When the Federal Reserve raises rates, each bank decides how much of the rise to pass on
            to its depositors. A bank that passes on little keeps its funding cheap; one that passes
            on a lot pays to keep its deposits. The share it passes on over a cycle is its{' '}
            <strong>deposit beta</strong>.
          </p>

          <h2 id="cycles">Two cycles, one fast and one slow</h2>
          <ChartCard
            built={rates}
            height={280}
            label="Line chart of the federal funds rate since 2008 with the two cycles shaded"
          />
          <p>
            The calibration cycle ran from {quarterLabel(calibration.start)} to{' '}
            {quarterLabel(calibration.end)}, taking the policy rate from{' '}
            {percent(calibration.startRate, 2)} to {percent(calibration.endRate, 2)} over{' '}
            {calibration.months} months. The test cycle ran from {quarterLabel(test.start)} to{' '}
            {quarterLabel(test.end)}, from {percent(test.startRate, 2)} to{' '}
            {percent(test.endRate, 2)} in {test.months}. Betas run higher in a cycle like the
            second, so levels are not compared. The test is of the <strong>ordering</strong>, by
            rank correlation, which a level shift does not move.
          </p>

          <h2 id="plan">The plan, fixed before the result</h2>
          <p>
            Written down on 10 October 2026, before any cross-cycle figure was computed (
            <a href={`${REPOSITORY}/blob/main/docs/decisions.md`}>decision 0034</a>).
          </p>
          <div className="plan-grid">
            <div className="card plan-card">
              <h3>Sample</h3>
              <p>
                Ranked banks with a tier 1 beta in both cycles, tier 1 cost of deposits in at least
                80 percent of each cycle’s quarters, no partial cycle and no material acquisition
                inside either cycle. No bank is excluded for the value of its beta.
              </p>
            </div>
            <div className="card plan-card">
              <h3>Test</h3>
              <p>
                Spearman correlation, judged by a one-sided permutation test (100,000 permutations)
                with a 95 percent bootstrap interval (10,000 resamples), seed 20261010. Persistence
                is supported if the correlation is positive with p below 0.05.
              </p>
            </div>
          </div>

          <h2 id="result">The result</h2>
          <div className="result-banner">
            <div className="result-number">{signed(headline.spearman)}</div>
            <div>
              <p>
                Spearman correlation across {headline.filers} banks, one-sided p{' '}
                {pValue(headline.p_value)}, 95% interval {signed(headline.interval_low)} to{' '}
                {signed(headline.interval_high)}.
              </p>
              <div className={headline.supported ? 'verdict verdict-yes' : 'verdict verdict-no'}>
                <Icon name={headline.supported ? 'check' : 'cross'} size={16} />
                {headline.supported
                  ? 'Persistence is supported by the rule fixed in advance'
                  : 'Persistence is not shown by the rule fixed in advance'}
              </div>
            </div>
          </div>
          <p>
            Each dot is a bank, placed by its rank in each cycle. A bank on the diagonal kept its
            exact place. The fast end holds best: the cluster at the top right is the same banks in
            both cycles, several of them direct banks with no branch network. The slow end is
            looser.
          </p>
          <ChartCard
            built={ranks}
            height={460}
            label="Scatter of each headline bank's rank in the two cycles"
          />
          <div className="aside">
            Secondary, and not the result, since levels are not expected to transfer: Pearson{' '}
            {signed(fit.pearson)}, and a least-squares fit of test beta on calibration beta with
            slope {fixed(fit.slope)} and R² {fixed(fit.r2)}. The median beta rose from{' '}
            {fixed(median(sample.map((b) => b.calibrationBeta)))} to{' '}
            {fixed(median(sample.map((b) => b.testBeta)))}.
          </div>

          <h2 id="robustness">Robust to every registered variant</h2>
          <ChartCard
            built={forest}
            height={320}
            label="Forest plot of the rank correlation and its interval for each registered sample"
          />

          <h2 id="survivorship">Survivorship strengthens it</h2>
          <p>
            A sample of banks that kept filing is survivors by construction. Silicon Valley Bank
            stopped filing inside the test cycle; First Republic and Signature never filed with the
            SEC, so their betas are recovered from their own Call Reports.
            {recoveredResult && (
              <>
                {' '}
                Adding all three takes the correlation to {signed(
                  recoveredResult.spearman,
                )} across {recoveredResult.filers} banks.
              </>
            )}{' '}
            Leaving out the failed banks, as an EDGAR-only study must, slightly understates the
            persistence.
          </p>
          <ChartCard
            built={survival}
            height={440}
            label="Scatter of deposit betas in both cycles with the failed banks highlighted"
          />

          <h2 id="movers">The banks that moved</h2>
          <p>
            Two or more quartiles apart between the cycles. Each hypothesis was formed after the
            result was seen, and only State Street’s has been tested.
          </p>
          <div className="mover-cards">
            {movers.map((m) => (
              <Link
                key={m.bank.cik}
                to={`/banks/${String(m.bank.cik)}`}
                className="card mover-card"
              >
                <h3>{m.bank.name}</h3>
                <div className="mover-path">
                  <span>
                    Q{m.calibrationQuartile} <small>{fixed(m.calibrationBeta, 3)}</small>
                  </span>
                  <Icon name="arrow" />
                  <span>
                    Q{m.testQuartile} <small>{fixed(m.testBeta, 3)}</small>
                  </span>
                </div>
              </Link>
            ))}
          </div>
          <ul className="hypotheses">
            <li>
              <strong>State Street.</strong> A custody bank with much of its deposits in other
              currencies, while euro rates stayed negative through 2015–2019. Tested against the
              Call Report split between domestic and foreign offices, the mechanism is there but
              does not explain the move: on its domestic offices alone State Street moves further.
              Its deviation is open.
            </li>
            <li>
              <strong>Zions.</strong> A commercially funded regional with a large uninsured base,
              exposed to the 2023 regional bank deposit flight in a way it was not in 2015–2019.
            </li>
            <li>
              <strong>Wells Fargo.</strong> Under the Federal Reserve’s asset cap throughout the
              test cycle, with little reason to pay for deposits it could not deploy. The cap came
              in February 2018, late in the calibration cycle.
            </li>
          </ul>

          <h2 id="validation">Is it the banks, or the tagging?</h2>
          <p>
            Every cost of deposits here is built from XBRL tags, and banks tag differently. So each
            one is checked against the cost computed from the same bank’s Call Reports. Each dot is
            a bank-quarter at tier 1.
          </p>
          <div className="inline-stats">
            <Stat value={count(validation.pairs)} label="bank-quarters compared" />
            <Stat value={validation.banks} label="banks" />
            <Stat value={basisPoints(validation.medianGapBp)} label="median gap" />
            <Stat value={percent(validation.withinTenBp, 0)} label="within 10 bp" />
          </div>
          <ChartCard
            built={checks}
            height={460}
            label="Scatter of cost of deposits from SEC filings against Call Reports for every tier 1 bank-quarter"
          />
          <p>
            Recomputed entirely on Call Report betas, and again on the Call Reports’ own average
            balances, the headline barely moves (
            <a href={`${METHODOLOGY}#7-validation-completed-so-far`}>methodology 7.5 and 7.6</a>).
            The persistence belongs to the banks, not to how their filings are tagged.
          </p>

          <h2 id="limits">What it does not show</h2>
          <ul className="limits">
            <li>
              A forecast for any one bank. The interval runs {signed(headline.interval_low)} to{' '}
              {signed(headline.interval_high)}.
            </li>
            <li>Anything about failure or distress.</li>
            <li>
              Three headline betas rest on an interest-bearing base that cannot be reconciled at one
              endpoint, and State Street’s move is unexplained. The{' '}
              <a href={METHODOLOGY}>methodology</a> lists every limitation, including those resolved
              unsatisfactorily.
            </li>
          </ul>
        </article>
      </div>
    </>
  );
}
