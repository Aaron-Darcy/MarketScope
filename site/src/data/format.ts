const MONTHS = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
];

const DASH = '–';

/** A signed figure, as correlations are reported: +0.59. */
export function signed(value: number, digits = 2): string {
  const text = Math.abs(value).toFixed(digits);
  return `${value < 0 ? '−' : '+'}${text}`;
}

export function fixed(value: number | null, digits = 2): string {
  return value === null ? DASH : value.toFixed(digits);
}

/** A fraction as a percentage: 0.0533 → 5.33%. */
export function percent(value: number | null, digits = 1): string {
  return value === null ? DASH : `${(value * 100).toFixed(digits)}%`;
}

export function basisPoints(value: number | null, digits = 1): string {
  return value === null ? DASH : `${value.toFixed(digits)} bp`;
}

export function count(value: number): string {
  return value.toLocaleString('en-US');
}

/** Dollars at the scale deposit balances are read: $1.2tn, $412bn, $38.0bn. */
export function dollars(value: number): string {
  if (Math.abs(value) >= 1e12) return `$${(value / 1e12).toFixed(2)}tn`;
  if (Math.abs(value) >= 1e11) return `$${(value / 1e9).toFixed(0)}bn`;
  if (Math.abs(value) >= 1e9) return `$${(value / 1e9).toFixed(1)}bn`;
  return `$${(value / 1e6).toFixed(0)}m`;
}

/** An ISO date's calendar quarter: 2022-03-31 → 2022Q1. */
export function quarterLabel(iso: string): string {
  const month = Number(iso.slice(5, 7));
  return `${iso.slice(0, 4)}Q${Math.ceil(month / 3)}`;
}

export function longDate(iso: string): string {
  const month = MONTHS[Number(iso.slice(5, 7)) - 1];
  if (month === undefined) throw new RangeError(`not an ISO date: ${iso}`);
  return `${Number(iso.slice(8, 10))} ${month} ${iso.slice(0, 4)}`;
}

/** The p-value to as many places as it takes to show its first significant digits. */
export function pValue(value: number): string {
  return value >= 0.01 ? value.toFixed(3) : value.toFixed(4);
}
