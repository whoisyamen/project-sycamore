import type { Snapshot } from '../data/types';
import { parseSnapshot } from '../data/validate';
export async function fetchSnapshot(fetcher: typeof fetch = fetch): Promise<Snapshot> {
  const response = await fetcher('/data/snapshot.json', {
    cache: 'no-store',
    signal: AbortSignal.timeout(15000),
  });
  if (!response.ok) throw new Error('Snapshot unavailable');
  return parseSnapshot(await response.json());
}
/** Reject older responses without discarding a last known good snapshot. */
export function acceptSnapshot(current: Snapshot | null, incoming: Snapshot): Snapshot {
  const stamp = (s: Snapshot) => s.manifest.lastAttempt ?? s.manifest.lastSync;
  return current && stamp(current) > stamp(incoming) ? current : incoming;
}
