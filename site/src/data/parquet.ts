import { parquetMetadata, parquetReadObjects } from 'hyparquet';

import { decodeRows, type RowOf, type TableSpec } from './schema';
import { TABLES, type TableName, type Tables } from './tables';

/** Read one exported table from its Parquet bytes and decode it against its spec. */
export async function readTable<S extends TableSpec>(
  table: string,
  spec: S,
  file: ArrayBuffer,
): Promise<RowOf<S>[]> {
  const metadata = parquetMetadata(file);
  const columns = metadata.schema.slice(1).map((element) => element.name);
  const wanted = Object.keys(spec).filter((column) => columns.includes(column));
  const raw = await parquetReadObjects({ file, metadata, columns: wanted });
  return decodeRows(table, spec, columns, raw);
}

/** Read every table the site uses, given a way to fetch each file's bytes. */
export async function readTables(
  fetchFile: (table: TableName) => Promise<ArrayBuffer>,
): Promise<Tables> {
  const names = Object.keys(TABLES) as TableName[];
  const decoded = await Promise.all(
    names.map(async (name) => [name, await readTable(name, TABLES[name], await fetchFile(name))]),
  );
  return Object.fromEntries(decoded) as Tables;
}
