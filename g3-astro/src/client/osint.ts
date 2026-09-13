// D-023: OSINT layer envelopes published by g3-ingest (flights/censys) and fetched client-side (seismic).
export interface FlightAircraft {
  id: string;
  cs?: string | null; // callsign, verbatim from OpenSky
  oc?: string | null; // origin country name, verbatim
  lon: number;
  lat: number;
  alt_m: number;
  v_ms?: number | null;
  hdg?: number | null;
}
export interface FlightsEnvelope {
  version: 1;
  ts: number; // ms epoch UTC of the OpenSky snapshot
  source: { name: string; endpoint: string };
  count: number;
  aircraft: FlightAircraft[];
  trails: Record<string, [number, number, number][]>; // [lon, lat, timestamp_ms], source fixes only
}

export interface CensysHost {
  ip: string;
  lon: number;
  lat: number;
  country_code?: string;
  ports?: number[];
  label?: string | null; // region that was queried for this host
}
export interface CensysEnvelope {
  version: 1;
  ts: number;
  source: { name: string; endpoint: string };
  count: number;
  hosts: CensysHost[];
}

/** Region spec the globe emits on selection (consumed by ingest for CENSYS sampling). */
export interface RegionSpec {
  kind: 'country' | 'bbox';
  name?: string; // English display name, required for country queries
  iso3?: string;
  country_code?: string; // two-letter ISO for hand-authored Censys country queries
  west?: number;
  south?: number;
  east?: number;
  north?: number;
}

export type LayerName = 'events' | 'flights' | 'seismic' | 'censys' | 'cities';
export type ImageryMode = 'dark' | 'satellite';

/** What the globe reports back to the dashboard when a region is picked. */
export interface RegionSelection {
  kind: 'country' | 'city';
  name: string;
  iso3?: string;
  lon: number;
  lat: number;
}
