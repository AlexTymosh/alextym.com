export const LAB_RECENT_LOGIN_SECONDS = 300;

export function isRecentLabLogin(authTime: number): boolean {
  const now = Date.now() / 1000;
  return Number.isSafeInteger(authTime) &&
    authTime > 0 && now - authTime <= LAB_RECENT_LOGIN_SECONDS && authTime <= now + 60;
}

export function isMatchingRecentLogin(
  session: { uid: string; auth_time: number },
  proof: { uid: string; auth_time: number },
): boolean {
  return Boolean(session.uid) && proof.uid === session.uid &&
    isRecentLabLogin(proof.auth_time) && proof.auth_time >= session.auth_time;
}
