import { create } from "zustand";
import { api, CampaignView, HistoryItem, Stream } from "@/lib/api";

type EditorState = {
  campaignId: number | null;
  campaign: CampaignView | null;
  history: HistoryItem[];
  loading: boolean;
  busyStream: number | null;
  error: string | null;
  /** черновик ручных долей: streamId -> offerId -> share */
  drafts: Record<number, Record<number, number>>;

  open: (id: number) => Promise<void>;
  reload: () => Promise<void>;
  close: () => void;
  addOffer: (streamId: number, offerId: number) => Promise<void>;
  removeOffer: (streamId: number, offerId: number) => Promise<void>;
  setDraft: (streamId: number, offerId: number, share: number) => void;
  resetDraft: (streamId: number) => void;
  saveShares: (streamId: number) => Promise<void>;
  clearError: () => void;
};

export const useEditor = create<EditorState>((set, get) => {
  const replaceStream = (s: Stream) =>
    set((st) => {
      if (!st.campaign) return {};
      const drafts = { ...st.drafts };
      delete drafts[s.id];
      return {
        campaign: { ...st.campaign, streams: st.campaign.streams.map((x) => (x.id === s.id ? s : x)) },
        drafts,
      };
    });

  const mutate = async (streamId: number, fn: () => Promise<Stream>) => {
    const cid = get().campaignId;
    if (!cid) return;
    set({ busyStream: streamId, error: null });
    try {
      replaceStream(await fn());
      api.history(cid).then((history) => set({ history })).catch(() => {});
    } catch (e) {
      set({ error: (e as Error).message });
    } finally {
      set({ busyStream: null });
    }
  };

  return {
    campaignId: null,
    campaign: null,
    history: [],
    loading: false,
    busyStream: null,
    error: null,
    drafts: {},

    open: async (id) => {
      set({ campaignId: id, campaign: null, history: [], drafts: {}, error: null });
      await get().reload();
    },
    reload: async () => {
      const id = get().campaignId;
      if (!id) return;
      set({ loading: true, error: null });
      try {
        const [campaign, history] = await Promise.all([api.campaign(id), api.history(id)]);
        set({ campaign, history, drafts: {} });
      } catch (e) {
        set({ error: (e as Error).message });
      } finally {
        set({ loading: false });
      }
    },
    close: () => set({ campaignId: null, campaign: null, history: [], drafts: {}, error: null }),

    addOffer: (sid, oid) => mutate(sid, () => api.addOffer(get().campaignId!, sid, oid)),
    removeOffer: (sid, oid) => mutate(sid, () => api.removeOffer(get().campaignId!, sid, oid)),

    setDraft: (sid, oid, share) =>
      set((st) => {
        const stream = st.campaign?.streams.find((s) => s.id === sid);
        const base = st.drafts[sid] ?? Object.fromEntries(stream?.offers.map((o) => [o.offer_id, o.share]) ?? []);
        return { drafts: { ...st.drafts, [sid]: { ...base, [oid]: share } } };
      }),
    resetDraft: (sid) =>
      set((st) => {
        const drafts = { ...st.drafts };
        delete drafts[sid];
        return { drafts };
      }),
    saveShares: (sid) => {
      const draft = get().drafts[sid];
      if (!draft) return Promise.resolve();
      return mutate(sid, () => api.setShares(get().campaignId!, sid, draft));
    },
    clearError: () => set({ error: null }),
  };
});
