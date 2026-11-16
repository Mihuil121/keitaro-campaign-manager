import { create } from "zustand";
import { api, Meta } from "@/lib/api";

type MetaState = {
  meta: Meta | null;
  loading: boolean;
  error: string | null;
  load: (force?: boolean) => Promise<void>;
};

export const useMeta = create<MetaState>((set, get) => ({
  meta: null,
  loading: false,
  error: null,
  load: async (force = false) => {
    if (get().loading || (get().meta && !force)) return;
    set({ loading: true, error: null });
    try {
      if (force) await api.clearCache();
      set({ meta: await api.meta() });
    } catch (e) {
      set({ error: (e as Error).message });
    } finally {
      set({ loading: false });
    }
  },
}));
