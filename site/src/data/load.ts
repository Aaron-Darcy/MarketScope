import bankEntityEvents from '../../../data/site/bank_entity_events.parquet?url';
import dimBank from '../../../data/site/dim_bank.parquet?url';
import dimRateCycle from '../../../data/site/dim_rate_cycle.parquet?url';
import fctBankQuarter from '../../../data/site/fct_bank_quarter.parquet?url';
import fctDepositBeta from '../../../data/site/fct_deposit_beta.parquet?url';
import martBankOverview from '../../../data/site/mart_bank_overview.parquet?url';
import martCrossBankComparison from '../../../data/site/mart_cross_bank_comparison.parquet?url';
import martPersistenceResult from '../../../data/site/mart_persistence_result.parquet?url';
import martRecoveredBeta from '../../../data/site/mart_recovered_beta.parquet?url';

import { buildSite, type Site } from './model';
import { readTables } from './parquet';
import type { TableName } from './tables';

// Imported by URL so the build copies each file under a content hash: a new export is a new
// URL, and a browser never pairs a cached table with a fresh one.
const URLS: Record<TableName, string> = {
  bank_entity_events: bankEntityEvents,
  dim_bank: dimBank,
  dim_rate_cycle: dimRateCycle,
  fct_bank_quarter: fctBankQuarter,
  fct_deposit_beta: fctDepositBeta,
  mart_bank_overview: martBankOverview,
  mart_cross_bank_comparison: martCrossBankComparison,
  mart_persistence_result: martPersistenceResult,
  mart_recovered_beta: martRecoveredBeta,
};

async function fetchTable(table: TableName): Promise<ArrayBuffer> {
  const response = await fetch(URLS[table]);
  if (!response.ok) throw new Error(`${table} could not be fetched: HTTP ${response.status}`);
  return response.arrayBuffer();
}

export async function loadSite(): Promise<Site> {
  return buildSite(await readTables(fetchTable));
}
