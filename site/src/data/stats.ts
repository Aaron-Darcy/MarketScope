import { median as d3Median, quantileSorted } from 'd3-array';

export function median(values: readonly number[]): number {
  const result = d3Median(values);
  if (result === undefined) throw new RangeError('median of no values');
  return result;
}

/** The p-quantile of values by linear interpolation, as DuckDB's `quantile_cont`. */
export function quantile(values: readonly number[], p: number): number {
  const result = quantileSorted(
    [...values].sort((a, b) => a - b),
    p,
  );
  if (result === undefined) throw new RangeError('quantile of no values');
  return result;
}

export interface Fit {
  readonly pearson: number;
  readonly slope: number;
  readonly intercept: number;
  readonly r2: number;
}

/** Pearson correlation and the least-squares fit of y on x. */
export function linearFit(points: readonly (readonly [number, number])[]): Fit {
  if (points.length < 3) throw new RangeError('a fit needs at least three points');
  const meanX = points.reduce((sum, [x]) => sum + x, 0) / points.length;
  const meanY = points.reduce((sum, [, y]) => sum + y, 0) / points.length;
  let sxx = 0;
  let syy = 0;
  let sxy = 0;
  for (const [x, y] of points) {
    sxx += (x - meanX) ** 2;
    syy += (y - meanY) ** 2;
    sxy += (x - meanX) * (y - meanY);
  }
  if (sxx === 0 || syy === 0) throw new RangeError('a fit needs variation in both x and y');
  const slope = sxy / sxx;
  const pearson = sxy / Math.sqrt(sxx * syy);
  return { pearson, slope, intercept: meanY - slope * meanX, r2: pearson * pearson };
}
