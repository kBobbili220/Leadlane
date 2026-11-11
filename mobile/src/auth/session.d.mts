import type { OwnerIdentity, OwnerSession } from "../api/auth.mjs";
export function restoreSession(options: {
  readToken: () => Promise<string | null>;
  loadIdentity: (token: string) => Promise<OwnerIdentity>;
  deleteToken: () => Promise<void>;
}): Promise<OwnerSession | null>;
