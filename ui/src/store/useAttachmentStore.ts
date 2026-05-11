/**
 * Attachment store — manage attachments, previews and upload progress.
 */
import { create } from "zustand";
import { devtools } from "zustand/middleware";
import { Attachment } from "@/types/models";

interface AttachmentStore {
  attachments: Map<string, Attachment>;
  uploadProgress: Map<string, number>;

  addLocalAttachment: (a: Attachment) => void;
  setProgress: (id: string, p: number) => void;
  markUploaded: (id: string, url?: string, metadata?: Record<string, any>) => void;
  getAttachment: (id: string) => Attachment | undefined;
  reset: () => void;
}

export const useAttachmentStore = create<AttachmentStore>()(
  devtools((set, get) => ({
    attachments: new Map(),
    uploadProgress: new Map(),

    addLocalAttachment: (a) =>
      set((state) => {
        const m = new Map(state.attachments);
        m.set(a.id, a);
        return { attachments: m };
      }),

    setProgress: (id, p) =>
      set((state) => {
        const m = new Map(state.uploadProgress);
        m.set(id, p);
        return { uploadProgress: m };
      }),

    markUploaded: (id, url, metadata) =>
      set((state) => {
        const m = new Map(state.attachments);
        const a = m.get(id);
        if (a) {
          m.set(id, { ...a, uploaded: true, url: url ?? a.url, metadata: { ...(a.metadata || {}), ...(metadata || {}) } });
        }
        const p = new Map(state.uploadProgress);
        p.delete(id);
        return { attachments: m, uploadProgress: p };
      }),

    getAttachment: (id) => get().attachments.get(id),

    reset: () => set({ attachments: new Map(), uploadProgress: new Map() }),
  }), { name: "AttachmentStore" })
);
