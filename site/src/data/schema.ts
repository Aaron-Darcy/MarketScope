/** Column kinds as the site reads them. Dates become ISO `YYYY-MM-DD` strings. */
export type Kind = 'string' | 'number' | 'integer' | 'boolean' | 'date';

export interface ColumnSpec<K extends Kind = Kind, N extends boolean = boolean> {
  readonly kind: K;
  readonly nullable: N;
}

export const required = <K extends Kind>(kind: K): ColumnSpec<K, false> => ({
  kind,
  nullable: false,
});

export const nullable = <K extends Kind>(kind: K): ColumnSpec<K, true> => ({
  kind,
  nullable: true,
});

export type TableSpec = Readonly<Record<string, ColumnSpec>>;

type ValueOf<K extends Kind> = K extends 'boolean'
  ? boolean
  : K extends 'number' | 'integer'
    ? number
    : string;

export type RowOf<S extends TableSpec> = {
  readonly [C in keyof S]: S[C] extends ColumnSpec<infer K, infer N>
    ? N extends true
      ? ValueOf<K> | null
      : ValueOf<K>
    : never;
};

/** A published table does not match what the site reads from it. */
export class SchemaError extends Error {
  override name = 'SchemaError';
}

function decodeValue(value: unknown, kind: Kind, where: string): string | number | boolean {
  switch (kind) {
    case 'string':
      if (typeof value === 'string') return value;
      break;
    case 'boolean':
      if (typeof value === 'boolean') return value;
      break;
    case 'number':
      // DuckDB writes NaN and infinities without complaint; no figure on the site is either.
      if (typeof value === 'number' && Number.isFinite(value)) return value;
      break;
    case 'integer': {
      // Parquet INT64 arrives as a BigInt. Every key and count the site reads fits in a double.
      const number = typeof value === 'bigint' ? Number(value) : value;
      if (typeof number === 'number' && Number.isSafeInteger(number)) return number;
      break;
    }
    case 'date':
      if (value instanceof Date && !Number.isNaN(value.getTime())) {
        return value.toISOString().slice(0, 10);
      }
      break;
  }
  throw new SchemaError(`${where} is not a ${kind}: ${String(value)}`);
}

/** Decode raw Parquet rows against a spec, refusing a missing column, an empty table or a stray null. */
export function decodeRows<S extends TableSpec>(
  table: string,
  spec: S,
  columns: readonly string[],
  raw: readonly Record<string, unknown>[],
): RowOf<S>[] {
  for (const column of Object.keys(spec)) {
    if (!columns.includes(column)) throw new SchemaError(`${table} has no column ${column}`);
  }
  if (raw.length === 0) throw new SchemaError(`${table} is empty`);

  return raw.map((source, index) => {
    const row: Record<string, string | number | boolean | null> = {};
    for (const [column, { kind, nullable: allowsNull }] of Object.entries(spec)) {
      const where = `${table}.${column}, row ${index}`;
      const value = source[column];
      if (value === null || value === undefined) {
        if (!allowsNull) throw new SchemaError(`${where} is null`);
        row[column] = null;
      } else {
        row[column] = decodeValue(value, kind, where);
      }
    }
    return row as RowOf<S>;
  });
}
