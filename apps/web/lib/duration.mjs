export const DURATION_UNITS = [
  { value: "minutes", label: "minutes", multiplier: 1 },
  { value: "hours", label: "hours", multiplier: 60 },
  { value: "days", label: "days", multiplier: 1440 },
];

export function durationToMinutes(value, unit) {
  if (value === "" || value === null || value === undefined) return null;
  const amount = Number(value);
  const selected = DURATION_UNITS.find((item) => item.value === unit);
  if (!Number.isFinite(amount) || amount < 0 || !selected) return null;
  return Math.round(amount * selected.multiplier);
}

export function minutesToDuration(minutes) {
  if (minutes === null || minutes === undefined) return { value: "", unit: "hours" };
  if (minutes !== 0 && minutes % 1440 === 0) return { value: String(minutes / 1440), unit: "days" };
  if (minutes !== 0 && minutes % 60 === 0) return { value: String(minutes / 60), unit: "hours" };
  return { value: String(minutes), unit: "minutes" };
}

export function formatDuration(minutes) {
  if (minutes === null || minutes === undefined) return "Not defined";
  if (minutes === 0) return "0 minutes";
  if (minutes % 1440 === 0) return `${minutes / 1440} day${minutes === 1440 ? "" : "s"}`;
  if (minutes % 60 === 0) return `${minutes / 60} hour${minutes === 60 ? "" : "s"}`;
  return `${minutes} minutes`;
}
