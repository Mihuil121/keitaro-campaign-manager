import { create } from "zustand";
import { api, CreatedCampaign, Meta, OfferRef } from "@/lib/api";

type Form = {
  name: string;
  geo: string;
  offer: OfferRef | null;
  domain_id: number | null;
  group_id: number | null;
  traffic_source_id: number | null;
};

type CreatorState = {
  form: Form;
  submitting: boolean;
  error: string | null;
  last: CreatedCampaign | null;
  created: CreatedCampaign[];
  setField: <K extends keyof Form>(k: K, v: Form[K]) => void;
  applyDefaults: (m: Meta) => void;
  loadCreated: () => Promise<void>;
  submit: () => Promise<CreatedCampaign | null>;
};

const empty: Form = { name: "", geo: "", offer: null, domain_id: null, group_id: null, traffic_source_id: null };

export const useCreator = create<CreatorState>((set, get) => ({
  form: empty,
  submitting: false,
  error: null,
  last: null,
  created: [],
  setField: (k, v) => set((s) => ({ form: { ...s.form, [k]: v }, error: null })),
  applyDefaults: (m) =>
    set((s) => ({
      form: {
        ...s.form,
        domain_id: s.form.domain_id ?? m.defaults.domain_id,
        group_id: s.form.group_id ?? m.defaults.group_id,
        traffic_source_id: s.form.traffic_source_id ?? m.defaults.traffic_source_id,
      },
    })),
  loadCreated: async () => {
    try {
      set({ created: await api.created() });
    } catch {
      /* история не критична */
    }
  },
  submit: async () => {
    const { form } = get();
    if (!form.name.trim()) return set({ error: "Введите название кампании" }), null;
    if (!form.geo.trim()) return set({ error: "Укажите гео" }), null;
    if (!form.offer) return set({ error: "Выберите оффер из списка" }), null;
    set({ submitting: true, error: null });
    try {
      const c = await api.createCampaign({
        name: form.name.trim(),
        geo: form.geo,
        offer_id: form.offer.id,
        domain_id: form.domain_id,
        group_id: form.group_id,
        traffic_source_id: form.traffic_source_id,
      });
      set((s) => ({
        last: c,
        created: [c, ...s.created],
        form: { ...s.form, name: "", geo: "", offer: null },
      }));
      return c;
    } catch (e) {
      set({ error: (e as Error).message });
      return null;
    } finally {
      set({ submitting: false });
    }
  },
}));
