export const REPOSITORY = 'https://github.com/Aaron-Darcy/MarketScope';

export const METHODOLOGY = `${REPOSITORY}/blob/main/docs/methodology.md`;

export function filingUrl(cik: number, accession: string): string {
  return `https://www.sec.gov/Archives/edgar/data/${String(cik)}/${accession.replaceAll('-', '')}/`;
}
