export const LAB_RECENT_LOGIN_SECONDS = 300;

export function isRecentLabLogin(authTime: number): boolean {
  const now = Date.now() / 1000;
  return Number.isSafeInteger(authTime) &&
    authTime > 0 && now - authTime <= LAB_RECENT_LOGIN_SECONDS && authTime <= now + 60;
}
