import { create } from "zustand";
import { SignedFileContainer } from "@/types/models";

export interface SignedFileItem {
  id: string;
  filename: string;
  size: number;
  signer: string;
  signed_at: string;
  algorithm: "Ed25519";
  hash: "SHA-256";
  container: SignedFileContainer;
}

interface SignatureStore {
  signedFiles: SignedFileItem[];
  addSignedFile: (item: SignedFileItem) => void;
  removeSignedFile: (id: string) => void;
  clearSignedFiles: () => void;
}

export const useSignatureStore =
  create<SignatureStore>((set) => ({
    signedFiles: [],
    addSignedFile: (item) =>
      set((state) => ({
        signedFiles: [item, ...state.signedFiles],
      })),
    removeSignedFile: (id) =>
      set((state) => ({
        signedFiles: state.signedFiles.filter(
          (item) => item.id !== id
        ),
      })),
    clearSignedFiles: () =>
      set({
        signedFiles: [],
      }),
  }));
