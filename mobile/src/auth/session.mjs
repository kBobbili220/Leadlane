/** Session restoration is testable without React Native or a physical device. */
export async function restoreSession({ readToken, loadIdentity, deleteToken }) {
  const token = await readToken();
  if (!token) return null;
  try {
    const identity = await loadIdentity(token);
    return { ...identity, access_token: token };
  } catch (error) {
    if (error.status === 401) { await deleteToken(); return null; }
    // A temporary network/server failure must not destroy remembered sessions.
    throw error;
  }
}
