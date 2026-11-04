import { useMemo } from 'react';
import { Link, useNavigate, useParams } from 'react-router';

import { useSite } from '../app/site';
import { useChartTheme } from '../app/theme';
import { costAgainstPolicy, depositsArea, peerStrip, tierStrip } from '../charts/bank';
import { Icon } from '../components/Icon';
import { filingUrl } from '../components/links';
import { ChartCard, Meter, Section, Stat, StatusPill, useDocumentTitle } from '../components/ui';
import { basisPoints, fixed, longDate, percent, quarterLabel } from '../data/format';
import {
  eventLabel,
  peerBand,
  peerPositions,
  type Bank,
  type CycleName,
  type Site,
} from '../data/model';
import { NotFound } from './NotFound';

function statusLine(bank: Bank): string {
  if (bank.exitDate === null) return 'Still filing';
  const date = longDate(bank.exitDate);
  switch (bank.status) {
    case 'merged':
      return `Merged into ${bank.exitCounterparty ?? 'another bank'} on ${date}`;
    case 'failed':
      return `Failed on ${date}`;
    case 'deregistered':
      return `Deregistered on ${date}`;
    case 'filing':
      return 'Still filing';
  }
}

function CycleCard({ bank, cycle }: { readonly bank: Bank; readonly cycle: CycleName }) {
  const beta = bank.betas[cycle];
  const years = cycle === 'calibration' ? '2015–2019' : '2022–2023';
  if (!beta) {
    return (
      <div className="card cycle-detail">
        <div className="eyebrow">{years} cycle</div>
        <p className="muted">No beta: the bank did not file through this cycle.</p>
      </div>
    );
  }
  const flags = [
    beta.partial_cycle && 'Cycle cut short',
    beta.material_event_in_cycle && 'Material acquisition inside the cycle',
    beta.tier_changes_in_cycle && 'Tier changes inside the cycle',
  ].filter((flag): flag is string => typeof flag === 'string');
  return (
    <div className="card cycle-detail">
      <div className="cycle-detail-head">
        <div className="eyebrow">{years} cycle</div>
        {beta.metric_tier && <span className="tier-chip">Tier {beta.metric_tier}</span>}
      </div>
      <div className="cycle-detail-beta">{fixed(beta.deposit_beta, 3)}</div>
      {beta.deposit_beta !== null && (
        <Meter
          share={Math.min(1, Math.max(0, beta.deposit_beta))}
          label={`Deposit beta ${fixed(beta.deposit_beta, 3)}`}
        />
      )}
      <dl className="cycle-detail-facts">
        <dt>Measured</dt>
        <dd>
          {quarterLabel(beta.start_quarter)} to {quarterLabel(beta.measured_end_quarter)}
        </dd>
        <dt>Its cost of deposits</dt>
        <dd>
          {percent(beta.start_cost_of_deposits, 2)} → {percent(beta.end_cost_of_deposits, 2)}
        </dd>
        <dt>Federal funds</dt>
        <dd>
          {percent(beta.start_rate_fraction, 2)} → {percent(beta.end_rate_fraction, 2)}
        </dd>
      </dl>
      {flags.length > 0 && (
        <ul className="flags">
          {flags.map((flag) => (
            <li key={flag}>{flag}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function peerSentence(site: Site, bank: Bank): string | null {
  const positions = peerPositions(site, bank);
  if (positions.length === 0) return null;
  const parts = positions.map(
    (p) =>
      `${String(p.slower)} of ${String(p.others)} other banks in ${p.cycle === 'calibration' ? '2015–2019' : '2022–2023'}`,
  );
  return `It passed on a larger share of the rate rise than ${parts.join(', and than ')}.`;
}

function BankView({ site, bank }: { readonly site: Site; readonly bank: Bank }) {
  useDocumentTitle(bank.name);
  const theme = useChartTheme();
  const navigate = useNavigate();
  const o = bank.overview;

  const band = useMemo(() => peerBand(site.quarters), [site]);
  const cost = useMemo(
    () => costAgainstPolicy(bank, site.policy, band, site.cycles, theme),
    [bank, site, band, theme],
  );
  const strip = useMemo(() => peerStrip(site.banks, bank, theme), [site, bank, theme]);
  const tiers = useMemo(() => tierStrip(bank, theme), [bank, theme]);
  const deposits = useMemo(() => depositsArea(bank, theme), [bank, theme]);
  const hasDeposits = bank.quarters.some(
    (q) => q.interest_bearing_deposits !== null || q.noninterest_bearing_deposits !== null,
  );

  const index = site.banks.indexOf(bank);
  const previous = site.banks[index - 1];
  const next = site.banks[index + 1];

  return (
    <>
      <section className="page-header bank-header">
        <div className="container">
          <nav className="breadcrumb" aria-label="Breadcrumb">
            <Link to="/banks">Banks</Link>
            <span aria-hidden="true">/</span>
            <span>{bank.name}</span>
          </nav>
          <div className="bank-header-row">
            <div>
              <div className="eyebrow eyebrow-light">
                {bank.rank !== null
                  ? `Ranked ${String(bank.rank)} of the largest fifty by peak total assets`
                  : 'Pinned beside the ranked fifty'}
              </div>
              <h1>{bank.name}</h1>
              <p className="bank-meta">
                <StatusPill status={bank.status} /> {statusLine(bank)} · {bank.sicDescription} · SEC
                CIK {bank.cik}
              </p>
            </div>
            <label className="select select-dark">
              <span>Jump to</span>
              <select value={bank.cik} onChange={(e) => void navigate(`/banks/${e.target.value}`)}>
                {site.banks.map((b) => (
                  <option key={b.cik} value={b.cik}>
                    {b.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="header-stats">
            <Stat tone="onDark" value={fixed(o.calibration_beta)} label="deposit beta, 2015–2019" />
            <Stat tone="onDark" value={fixed(o.test_beta)} label="deposit beta, 2022–2023" />
            <Stat
              tone="onDark"
              value={percent(o.tier_1_share, 0)}
              label={`of ${String(o.cost_quarters)} quarters at tier 1, ${o.first_cost_quarter.slice(0, 4)}–${o.last_cost_quarter.slice(0, 4)}`}
            />
            <Stat
              tone="onDark"
              value={basisPoints(o.median_regulatory_gap_bp)}
              label="median gap to its Call Reports"
            />
          </div>
        </div>
      </section>

      {bank.pinnedReason && (
        <div className="container">
          <p className="notice">{bank.pinnedReason}</p>
        </div>
      )}

      <Section
        eyebrow="Pricing"
        title="What it paid depositors, against the Fed"
        intro={
          <p>
            Interest expense on deposits, annualised, over the average deposit base: from the bank’s
            SEC filings and, as a check, from its own Call Reports. Where the two agree they draw as
            one line. The shaded band is the middle half of every bank that quarter. Drag the slider
            to zoom.
          </p>
        }
      >
        <ChartCard
          built={cost}
          height={440}
          label={`Line chart of ${bank.name}'s cost of deposits against the federal funds rate`}
        />
      </Section>

      <Section
        tint
        eyebrow="Peers"
        title="Where it sits among its peers"
        intro={<p>{peerSentence(site, bank) ?? 'It has no deposit beta in either cycle.'}</p>}
      >
        <ChartCard
          subtitle="Every bank’s deposit beta in each cycle, this one highlighted. Select another dot to open that bank."
          built={strip}
          height={240}
          label={`Strip chart of every bank's deposit beta with ${bank.name} highlighted`}
        />
        <div className="cycle-details">
          <CycleCard bank={bank} cycle="calibration" />
          <CycleCard bank={bank} cycle="test" />
        </div>
      </Section>

      <Section eyebrow="Data quality" title="Comparability tier, quarter by quarter">
        <ChartCard
          built={tiers}
          height={130}
          label={`Strip of ${bank.name}'s comparability tier for each quarter`}
        />
      </Section>

      <Section tint eyebrow="Balance sheet" title="Deposits">
        {hasDeposits ? (
          <ChartCard
            built={deposits}
            height={320}
            label={`Stacked area chart of ${bank.name}'s interest-bearing and non-interest-bearing deposits`}
          />
        ) : (
          <p className="muted">
            This bank tags neither an interest-bearing nor a non-interest-bearing deposit balance.
          </p>
        )}
      </Section>

      <Section
        eyebrow="Corporate events"
        title="Mergers, exits and failures"
        intro={
          bank.events.length > 0 ? (
            <p>
              Each links to the filing that reports it. An acquisition is material when it moves the
              deposit base by a tenth or more in the quarter it completes.
            </p>
          ) : undefined
        }
      >
        {bank.events.length === 0 ? (
          <p className="muted">No merger, exit or failure is recorded for this bank.</p>
        ) : (
          <ol className="timeline">
            {bank.events.map((event) => (
              <li key={`${event.event_date}-${event.event_type}-${event.counterparty ?? ''}`}>
                <div className="timeline-date">{longDate(event.event_date)}</div>
                <div className="timeline-body">
                  <strong>{eventLabel(event.event_type)}</strong>
                  {event.counterparty && <> · {event.counterparty}</>}
                  {event.deposit_step !== null && (
                    <span className="muted"> · deposits {percent(event.deposit_step, 1)}</span>
                  )}
                  {event.material && <span className="tier-chip">Material</span>}
                  <a href={filingUrl(bank.cik, event.evidence_accession)} className="text-link">
                    {event.evidence_form} <Icon name="external" size={13} />
                  </a>
                </div>
              </li>
            ))}
          </ol>
        )}
      </Section>

      <div className="container pager">
        {previous ? (
          <Link to={`/banks/${String(previous.cik)}`} className="card pager-link">
            <Icon name="back" /> <span>{previous.name}</span>
          </Link>
        ) : (
          <span />
        )}
        {next && (
          <Link to={`/banks/${String(next.cik)}`} className="card pager-link pager-next">
            <span>{next.name}</span> <Icon name="arrow" />
          </Link>
        )}
      </div>
    </>
  );
}

export function BankPage() {
  const site = useSite();
  const { cik } = useParams();
  const bank = site.bankByCik.get(Number(cik));
  if (!bank) return <NotFound message={`No bank in the universe has CIK ${cik ?? ''}.`} />;
  return <BankView key={bank.cik} site={site} bank={bank} />;
}
