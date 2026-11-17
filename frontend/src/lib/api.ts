export type Ref = { id: number; name: string };

export type Meta = {
  domains: Ref[];
  groups: Ref[];
  sources: Ref[];
  campaign_prefix: string;
  defaults: { domain_id: number | null; group_id: number | null; traffic_source_id: number | null };
};

export type OfferRef = { id: number; name: string; state?: string };

export type CreatedCampaign = {
  id: number;
  name: string;
  alias: string;
  geo: string[];
  offer_id: number;
  url: string | null;
  geo_stream_id: number;
  offer_stream_id: number;
  created_at: string | null;
};

export type StreamOffer = { offer_id: number; name: string; share: number; state: string };

export type Stream = {
  id: number;
  name: string;
  type: string;
  schema: string;
  position: number;
  state: string;
  action_payload: string | null;
  filters: { name: string; mode: string; payload: unknown }[];
  offers: StreamOffer[];
  shares_total: number;
};

export type CampaignView = { id: number; name: string; alias: string; state: string; streams: Stream[] };
export type CampaignRef = { id: number; name: string; alias: string; state: string };

export type HistoryItem = {
  id: number;
  stream_id: number;
  action: "add" | "remove" | "set_shares";
  offer_id: number | null;
  before: { offer_id: number; share: number }[];
  after: { offer_id: number; share: number }[];
  created_at: string | null;
};

async function req<T>(method: string, url: string, body?: unknown): Promise<T> {
  const r = await fetch(url, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const data = await r.json().catch(() => null);
  if (!r.ok) {
    const d = data?.detail;
    const msg = typeof d === "string" ? d : Array.isArray(d) ? d.map((e: { msg: string }) => e.msg).join("; ") : `Ошибка ${r.status}`;
    throw new Error(msg);
  }
  return data as T;
}

const q = (params: Record<string, string>) => new URLSearchParams(params).toString();

export const api = {
  meta: () => req<Meta>("GET", "/api/meta"),
  clearCache: () => req("POST", "/api/cache/clear"),
  offers: (query: string) => req<OfferRef[]>("GET", `/api/offers?${q({ q: query })}`),
  createCampaign: (body: {
    name: string;
    geo: string;
    offer_id: number;
    domain_id: number | null;
    group_id: number | null;
    traffic_source_id: number | null;
  }) => req<CreatedCampaign>("POST", "/api/campaigns", body),
  created: () => req<CreatedCampaign[]>("GET", "/api/campaigns/created"),
  campaigns: (query: string) => req<CampaignRef[]>("GET", `/api/campaigns?${q({ q: query })}`),
  campaign: (id: number) => req<CampaignView>("GET", `/api/campaigns/${id}`),
  history: (id: number) => req<HistoryItem[]>("GET", `/api/campaigns/${id}/history`),
  addOffer: (cid: number, sid: number, offerId: number) =>
    req<Stream>("POST", `/api/campaigns/${cid}/streams/${sid}/offers`, { offer_id: offerId }),
  removeOffer: (cid: number, sid: number, offerId: number) =>
    req<Stream>("DELETE", `/api/campaigns/${cid}/streams/${sid}/offers/${offerId}`),
  setShares: (cid: number, sid: number, shares: Record<number, number>) =>
    req<Stream>("PUT", `/api/campaigns/${cid}/streams/${sid}/shares`, { shares }),
};
