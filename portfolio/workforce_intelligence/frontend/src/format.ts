import type { Observation, Window } from "./data-api";

const number = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 3 });
const day = new Intl.DateTimeFormat("en-GB", {
  day: "numeric", month: "short", year: "numeric", timeZone: "UTC",
});
const time = new Intl.DateTimeFormat("en-GB", {
  day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/London",
});

export const displayNumber = (value: number) => number.format(value);
export const displayDay = (value: string) => day.format(new Date(value));
export const displayRefresh = (value: string) => time.format(new Date(value));
export const displayWindow = (value: Window) => `${displayDay(value.start)} to ${displayDay(value.end)}`;

export function displayObservation(observation: Observation, unit = "") {
  if (observation.status === "suppressed") return "Suppressed";
  if (observation.value === null || observation.status !== "available") return "Not available";
  const suffix = unit === "%" ? "%" : unit ? ` ${unit}` : "";
  return `${displayNumber(observation.value)}${suffix}`;
}

export function displayCode(code: string) {
  const label = code.replaceAll("_", " ");
  return label.charAt(0).toUpperCase() + label.slice(1);
}
