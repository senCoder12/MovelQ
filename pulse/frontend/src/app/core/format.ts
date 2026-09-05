// Shared number formatting. Counts and money follow the Indian grouping the
// operators read in their own reports ("1,17,605"), percentages do not group.

const COUNT = new Intl.NumberFormat('en-IN');
const INR = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 });

export function formatCount(value: number): string {
  return COUNT.format(value);
}

export function formatInr(value: number): string {
  return `₹${INR.format(value)}`;
}

/** Trims a float to at most one decimal without padding whole numbers. */
export function formatPct(value: number): string {
  return `${Math.round(value * 10) / 10}%`;
}

/** Minutes at tile width: 1.38 -> "1.4m". */
export function formatMinutes(value: number): string {
  return `${Math.round(value * 10) / 10}m`;
}

const LAKH = 100_000;
const CRORE = 10_000_000;

/**
 * Indian short scale, the way these numbers get spoken in an operations review:
 * 215,885 -> "2.16L", 28,70,000 -> "28.7L", 4,20,00,000 -> "4.2Cr". Anything
 * under a lakh keeps its full grouping, since shortening it loses precision
 * without saving space.
 */
export function formatCompact(value: number): string {
  if (Math.abs(value) >= CRORE) {
    return `${trim(value / CRORE)}Cr`;
  }
  if (Math.abs(value) >= LAKH) {
    return `${trim(value / LAKH)}L`;
  }
  return COUNT.format(value);
}

export function formatCompactInr(value: number): string {
  return `₹${formatCompact(value)}`;
}

/**
 * Two decimals below ten, one above, and never a trailing ".0". Single-digit
 * lakh figures carry most of their precision after the point -- "1.2L" throws
 * away 5,000 trips that "1.18L" keeps, at no extra width.
 */
function trim(value: number): string {
  const places = Math.abs(value) < 10 ? 2 : 1;
  const factor = 10 ** places;
  const rounded = Math.round(value * factor) / factor;
  return Number.isInteger(rounded) ? String(rounded) : String(rounded);
}
