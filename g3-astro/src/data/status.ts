import type { Manifest } from './types';
export function dataStatus(
  manifest: Manifest | null,
  demo = false,
  disconnected = false,
  now = Date.now(),
) {
  if (demo)
    return {
      kind: 'demo',
      label: 'Demo · fictional events',
      detail: 'Demo mode uses illustrative data.',
    };
  if (!manifest)
    return {
      kind: 'error',
      label: 'Data unavailable',
      detail: 'Waiting for a valid event update.',
    };
  const mins = Math.max(0, Math.floor((now - manifest.lastSync) / 60000));
  const age =
    mins < 1
      ? 'just now'
      : mins < 60
        ? `${mins}m ago`
        : mins < 1440
          ? `${Math.floor(mins / 60)}h ago`
          : `${Math.floor(mins / 1440)}d ago`;
  const detail = manifest.lastSync
    ? `Last successful source check ${age}.`
    : 'No successful source check yet.';
  if (manifest.health.status === 'error')
    return { kind: 'error', label: 'Sources unavailable', detail };
  if (disconnected) return { kind: 'delayed', label: 'Connection interrupted', detail };
  if (!manifest.lastSync || mins >= 30)
    return { kind: 'delayed', label: `Data delayed · ${age}`, detail };
  if (manifest.health.status === 'degraded')
    return { kind: 'delayed', label: 'Some sources unavailable', detail };
  return { kind: 'ok', label: `Updated ${age}`, detail };
}
