import type { Event } from '../data/types';

export interface EventMap {
  update(events: Event[], active: number | null): void;
  focus(id: number): void;
  resize(): void;
  setPresentationMode?(enabled: boolean): void;
  destroy(): void;
}
