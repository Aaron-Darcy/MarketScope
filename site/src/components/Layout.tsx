import { Suspense, useState } from 'react';
import { Link, NavLink, Outlet, ScrollRestoration, useLocation } from 'react-router';

import { useThemeMode } from '../app/theme';
import { ErrorBoundary } from './ErrorBoundary';
import { GithubMark, Icon } from './Icon';
import { METHODOLOGY, REPOSITORY } from './links';

const NAV = [
  { to: '/', label: 'Overview', end: true },
  { to: '/banks', label: 'Banks', end: false },
  { to: '/comparison', label: 'Comparison', end: false },
  { to: '/persistence', label: 'Case study', end: false },
] as const;

function Logo() {
  return (
    <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="8" fill="#0d366b" />
      <path
        d="M7 22l6-7 5 4 7-9"
        fill="none"
        stroke="#86b6ef"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="25" cy="10" r="2.5" fill="#eb6834" />
    </svg>
  );
}

function Header() {
  const { mode, toggle } = useThemeMode();
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  const [openedAt, setOpenedAt] = useState(pathname);
  if (openedAt !== pathname) {
    setOpenedAt(pathname);
    setOpen(false);
  }

  return (
    <header className="site-header">
      <div className="container header-inner">
        <Link to="/" className="brand">
          <Logo />
          <span>MarketScope</span>
        </Link>
        <nav className={open ? 'nav open' : 'nav'} aria-label="Main">
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} className="nav-link">
              {item.label}
            </NavLink>
          ))}
          <a className="nav-link" href={METHODOLOGY}>
            Methodology
          </a>
        </nav>
        <div className="header-actions">
          <button
            type="button"
            className="icon-button"
            onClick={toggle}
            aria-label={mode === 'light' ? 'Switch to dark theme' : 'Switch to light theme'}
          >
            <Icon name={mode === 'light' ? 'moon' : 'sun'} />
          </button>
          <a className="icon-button" href={REPOSITORY} aria-label="Source on GitHub">
            <GithubMark />
          </a>
          <button
            type="button"
            className="icon-button menu-button"
            onClick={() => {
              setOpen(!open);
            }}
            aria-expanded={open}
            aria-label="Menu"
          >
            <Icon name={open ? 'cross' : 'menu'} />
          </button>
        </div>
      </div>
    </header>
  );
}

function Footer() {
  return (
    <footer className="site-footer">
      <div className="container footer-grid">
        <div>
          <div className="brand footer-brand">
            <Logo />
            <span>MarketScope</span>
          </div>
          <p>
            Deposit pricing at the largest US banks across two tightening cycles, built from SEC
            EDGAR XBRL filings and FRED, and checked against FDIC and FFIEC Call Reports.
          </p>
        </div>
        <div>
          <h4>Explore</h4>
          {NAV.map((item) => (
            <Link key={item.to} to={item.to}>
              {item.label}
            </Link>
          ))}
        </div>
        <div>
          <h4>Method</h4>
          <a href={METHODOLOGY}>Methodology</a>
          <a href={`${REPOSITORY}/blob/main/docs/specification.md`}>Specification</a>
          <a href={`${REPOSITORY}/blob/main/docs/decisions.md`}>Decision log</a>
          <a href={REPOSITORY}>Source code</a>
        </div>
      </div>
      <div className="container footer-note">
        Figures are rebuilt from the committed data export on every deploy. Nothing here is a
        forecast or investment advice.
      </div>
    </footer>
  );
}

function Loading() {
  return (
    <div className="loading" role="status">
      <div className="spinner" />
      <span>Reading the data export…</span>
    </div>
  );
}

export function Layout() {
  const { pathname } = useLocation();
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <Header />
      <main id="main">
        <ErrorBoundary key={pathname}>
          <Suspense fallback={<Loading />}>
            <Outlet />
          </Suspense>
        </ErrorBoundary>
      </main>
      <Footer />
      <ScrollRestoration />
    </>
  );
}
