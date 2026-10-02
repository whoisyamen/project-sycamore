import type { Event } from '../data/types';

export interface EventMap {
  update(events: Event[], active: number | null): void;
  focus(id: number): void;
  resize(): void;
  /** Re-fit the disc to the stage band, e.g. after a chrome panel collapses. */
  reframe?(): void;
  setPresentationMode?(enabled: boolean): void;
  /** Pause the globe render loop while another surface (the feed) is showing. */
  setSuspended?(suspended: boolean): void;
  destroy(): void;
}
