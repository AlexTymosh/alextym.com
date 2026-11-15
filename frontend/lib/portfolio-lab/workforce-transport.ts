const entity = "[a-z0-9][a-z0-9-]{0,63}";
const pagination = ["limit", "offset", "as_of_date"];
const reportingWindow = ["as_of_date", "period_start"];

const operations: readonly [string, RegExp, readonly string[]][] = [
  ["GET", /^(status|demo\/status|metrics)$/, []],
  ["GET", /^(employees|vacancies|analytics\/vacancy-lifecycle)$/, pagination],
  ["GET", /^analytics\/executive$/, reportingWindow],
  ["GET", /^analytics\/candidate-funnel$/, [...reportingWindow, "vacancy_id"]],
  ["GET", /^data-quality$/, ["as_of_date"]],
  ["PATCH", new RegExp(`^employees/${entity}/contracts$`), []],
  ["POST", new RegExp(`^vacancies/${entity}/cancel$`), []],
  ["POST", /^(starters|demo\/reset)$/, []],
];

export function workforceUpstreamPath(method: string, parts: string[], query: URLSearchParams) {
  // Reject encoded separators, dot segments and other delimiters before assembling a path.
  if (!parts.every((part) => part.length <= 64 && /^[a-z0-9]/.test(part) && !/[^a-z0-9-]/.test(part))) {
    return null;
  }
  const path = parts.join("/");
  const operation = operations.find(([verb, pattern]) => verb === method && pattern.test(path));
  if (!operation) return null;

  const search = new URLSearchParams();
  for (const [key, value] of Array.from(query.entries())) {
    if (!operation[2].includes(key) || search.has(key) || !value || value.length > 64) return null;
    search.set(key, value);
  }
  return `/api/workforce/${path}${search.size ? `?${search}` : ""}`;
}
