/** An optional game-only display label. It never selects a login or a grant. */
export function preferansAlias(value: unknown): string | null {
  if (typeof value !== "string" || value.length > 40 || /[@\u0000-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/.test(value)) return null;
  return value.trim();
}
export function aliasChange(value: unknown): {uid:string; alias:string} | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const v = value as Record<string,unknown>;
  if (Object.keys(v).length !== 2 || typeof v.uid !== "string" || !v.uid || v.uid.length > 128 || /[\/\u0000-\u001f\u007f-\u009f]/.test(v.uid) || v.uid === "." || v.uid === "..") return null;
  const alias = preferansAlias(v.alias);
  return alias === null ? null : {uid:v.uid,alias};
}
