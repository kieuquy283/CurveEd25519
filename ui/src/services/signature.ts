import { buildApiBaseCandidates, getApiBaseUrl } from "@/config/env";
import {
  SignatureDebug,
  SignedFileContainer,
  VerificationResult,
} from "@/types/models";

export async function signFile(params: {
  signer: string;
  filename: string;
  mime_type: string;
  content_b64: string;
}): Promise<{
  ok: boolean;
  signed_file: SignedFileContainer;
  debug: SignatureDebug;
}> {
  const bases = buildApiBaseCandidates(getApiBaseUrl());
  let lastNetworkError: unknown;

  for (const base of bases) {
    let response: Response;

    try {
      response = await fetch(`${base}/api/signature/sign-file`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(params),
      });
    } catch (error) {
      lastNetworkError = error;
      continue;
    }

    if (!response.ok) {
      let detail = "";
      try {
        const json = (await response.json()) as { detail?: string };
        detail = json.detail ?? "";
      } catch {
        detail = await response.text();
      }
      throw new Error(
        `Sign-file failed (${response.status}) at ${base}: ${detail || "Unknown error"}`
      );
    }

    return response.json();
  }

  throw new Error(
    `Backend signature API unreachable at ${bases.join(" or ")}. ${
      lastNetworkError instanceof Error ? `Cause: ${lastNetworkError.message}` : ""
    }`.trim()
  );
}

export async function verifySignedFile(params: {
  signed_file: SignedFileContainer;
  verifier?: string;
  expected_signer?: string;
}): Promise<VerificationResult> {
  const bases = buildApiBaseCandidates(getApiBaseUrl());
  let lastNetworkError: unknown;

  for (const base of bases) {
    let response: Response;

    try {
      response = await fetch(`${base}/api/signature/verify-file`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(params),
      });
    } catch (error) {
      lastNetworkError = error;
      continue;
    }

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Verify-file failed (${response.status}) at ${base}: ${text}`);
    }

    return response.json();
  }

  throw new Error(
    `Backend signature API unreachable at ${bases.join(" or ")}. ${
      lastNetworkError instanceof Error ? `Cause: ${lastNetworkError.message}` : ""
    }`.trim()
  );
}
