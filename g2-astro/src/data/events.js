// SAMPLE DATA — fictional events, no real attribution. Real data lands in G2 via GDELT ingest.
// Rebalanced from the g1 prototype: 8 cyber / 5 geopolitical / 3 maritime / 1 military

export const TOPICS = {
  cyber:       { label: 'CYBER',       color: '#3DF7FF' },
  geopolitical:{ label: 'GEOPOLITICAL',color: '#F5A524' },
  maritime:    { label: 'MARITIME',    color: '#2EE59D' },
  military:    { label: 'MILITARY',    color: '#FF3B5C' }
};

export const EVENTS = [
  // ── 8 CYBER ──────────────────────────────────────────────────────────────
  { id: 1,  t: 'cyber',       sev: 'critical', title: 'Major utility control-system breach attributed to state-adjacent cluster; billing portal offline 14h',
    src: 'Vendor advisory (anonymized)',  loc: 'Frankfurt, DE',          lat: 50.11, lon: 8.68 },
  { id: 2,  t: 'cyber',       sev: 'critical', title: 'Healthcare clearinghouse ransomware spreads via managed-service provider; 23 facilities diverting patients',
    src: 'Sector ISAC bulletin',          loc: 'Chicago, US',            lat: 41.88, lon: -87.63 },
  { id: 3,  t: 'cyber',       sev: 'escalating', title: 'Coordinated spear-phishing campaign targets election infrastructure officials in three provinces',
    src: 'CERT advisory',                loc: 'Toronto, CA',            lat: 43.65, lon: -79.38 },
  { id: 4,  t: 'cyber',       sev: 'escalating', title: 'Cloud-storage misconfiguration exposes 4.1M customer records; firm begins notification process',
    src: 'Regulatory filing',            loc: 'Singapore, SG',          lat: 1.35,  lon: 103.82 },
  { id: 5,  t: 'cyber',       sev: 'watching',  title: 'DDoS against financial regulator sustained for 6h; origin points span 14 jurisdictions',
    src: 'Outage tracker',               loc: 'Brasília, BR',           lat: -15.79,lon: -47.88 },
  { id: 6,  t: 'cyber',       sev: 'watching',  title: 'AI-generated deepfake CFO audio used in successful wire-fraud attempt, $25M recovered',
    src: 'Court filing',                 loc: 'London, UK',             lat: 51.51, lon: -0.13 },
  { id: 7,  t: 'cyber',       sev: 'deesc',     title: 'Vulnerability in widely deployed VPN appliance disclosed; patches available, adoption uneven',
    src: 'Vendor security bulletin',     loc: 'San José, US',           lat: 37.34, lon: -121.89 },
  { id: 8,  t: 'cyber',       sev: 'deesc',     title: 'Botnet takedown coordinated across 11 countries; sinkhole operation entered cleanup phase',
    src: 'Joint press statement',        loc: 'The Hague, NL',          lat: 52.07, lon: 4.30 },

  // ── 5 GEOPOLITICAL ───────────────────────────────────────────────────────
  { id: 9,  t: 'geopolitical',sev: 'critical', title: 'Multilateral sanctions package enters force; three firms added to restricted-entity list',
    src: 'Official gazette',             loc: 'Brussels, BE',           lat: 50.85, lon: 4.35 },
  { id: 10, t: 'geopolitical',sev: 'escalating', title: 'Cross-strait diplomatic channel reopens after 11-month freeze; trade talks scheduled',
    src: 'Joint communiqué',             loc: 'Taipei, TW',             lat: 25.03, lon: 121.57 },
  { id: 11, t: 'geopolitical',sev: 'escalating', title: 'Border-trade agreement collapses after certification dispute; tariffs snap back',
    src: 'Ministry statement',           loc: 'Lagos, NG',              lat: 6.52,  lon: 3.38 },
  { id: 12, t: 'geopolitical',sev: 'watching',  title: 'Election monitoring mission deployed; pre-vote assessment notes uneven media access',
    src: 'Observer group report',        loc: 'Jakarta, ID',            lat: -6.21, lon: 106.85 },
  { id: 13, t: 'geopolitical',sev: 'deesc',     title: 'Humanitarian corridor reopens under neutral monitoring; aid convoy cleared',
    src: 'UN logistics note',            loc: 'Gaza, PS',               lat: 31.35, lon: 34.31 },

  // ── 3 MARITIME ───────────────────────────────────────────────────────────
  { id: 14, t: 'maritime',    sev: 'escalating', title: 'Submarine cable fault in Red Sea disrupts 17% of Europe-Asia traffic; repair ship en route',
    src: 'Cable operator',               loc: 'Red Sea, INT',           lat: 19.5,  lon: 38.5 },
  { id: 15, t: 'maritime',    sev: 'watching',  title: 'War-risk insurance premiums rise 18% for Hormuz transits after two near-miss incidents',
    src: 'Lloyd\'s market update',       loc: 'Strait of Hormuz, INT',  lat: 26.6,  lon: 56.25 },
  { id: 16, t: 'maritime',    sev: 'deesc',     title: 'Container terminal cyber incident contained; backlog clearing, no data exfiltration confirmed',
    src: 'Port authority release',       loc: 'Rotterdam, NL',          lat: 51.92, lon: 4.48 },

  // ── 1 MILITARY (single example, per the rebalance) ───────────────────────
  { id: 17, t: 'military',    sev: 'watching',  title: 'Multinational exercise window closes on schedule; no incidents reported',
    src: 'Joint task force statement',   loc: 'Baltic Sea, INT',        lat: 58.0,  lon: 21.0 }
];

export const OUTLOOKS = [
  { t: 'Critical infrastructure targeting',  c: 78, d: '90 days' },
  { t: 'AI-enabled fraud',                     c: 71, d: '60 days' },
  { t: 'Submarine cable incidents',            c: 64, d: '30 days' },
  { t: 'Sanctions enforcement volatility',     c: 58, d: '60 days' },
  { t: 'Election interference',                c: 52, d: '90 days' }
];

export const MARKETS = [
  ['LMT',   'Lockheed Martin',  '585.40', '-0.8%'],
  ['RHM.DE','Rheinmetall',      '682.10', '+2.1%'],
  ['RTX',   'RTX Corp',         '112.93', '-0.3%'],
  ['OXY',   'Occidental',        '62.18', '+0.9%'],
  ['GLD',   'Gold ETF',         '241.55', '+0.4%']
];
