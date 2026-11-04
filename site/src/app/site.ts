import { use } from 'react';

import { loadSite } from '../data/load';
import type { Site } from '../data/model';

let pending: Promise<Site> | undefined;

/** The site's data, loaded once on first use; suspends until every table has been read. */
export function useSite(): Site {
  pending ??= loadSite();
  return use(pending);
}
