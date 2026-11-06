/** The speeds of the maps made in advance (see GenerateSpeedMapsModal); the server checks the same limits. */
export const MAX_SPEEDS = 20;
export const MIN_SPEED_KT = 20;
export const MAX_SPEED_KT = 400;

/** The speeds from `from` to `to` in steps of `step`, both ends included when the step reaches them. */
export function speedsInRange(from: number, to: number, step: number): number[] {
  if (![from, to, step].every(Number.isFinite) || step <= 0 || to < from) return [];
  const speeds: number[] = [];
  // Counted in whole steps, so 0.1 steps do not drift
  for (let index = 0; from + index * step <= to + 1e-9 && speeds.length <= MAX_SPEEDS * 5; index += 1) {
    speeds.push(Math.round((from + index * step) * 1000) / 1000);
  }
  return speeds;
}

/** The speeds with the new ones added, each once, slowest first. */
export function addSpeeds(speeds: number[], added: number[]): number[] {
  return Array.from(new Set([...speeds, ...added])).sort((a, b) => a - b);
}

/** What is wrong with the speeds and the wind, or null. */
export function speedMapsProblem(speeds: number[], windSpeed: number, windDirection: number): string | null {
  if (speeds.length === 0) return 'Add at least one speed.';
  if (speeds.length > MAX_SPEEDS) return `At most ${MAX_SPEEDS} speeds: remove ${speeds.length - MAX_SPEEDS}.`;
  if (speeds.some((speed) => speed < MIN_SPEED_KT || speed > MAX_SPEED_KT)) {
    return `Speeds are between ${MIN_SPEED_KT} and ${MAX_SPEED_KT} knots.`;
  }
  if (!Number.isFinite(windSpeed) || windSpeed < 0 || windSpeed > 100) return 'The wind speed is between 0 and 100 knots.';
  if (!Number.isFinite(windDirection) || windDirection < 0 || windDirection > 360) {
    return 'The wind direction is between 0 and 360 degrees.';
  }
  // The gate times are planned at the ground speed, which the wind must leave positive
  if (windSpeed >= Math.min(...speeds)) return `The wind speed must be lower than the slowest speed (${Math.min(...speeds)} knots).`;
  return null;
}
