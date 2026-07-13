export function monthKey(date) {
  const y = date.getUTCFullYear();
  const m = String(date.getUTCMonth() + 1).padStart(2, '0');
  return `trial:${y}-${m}`;
}

export function isOverCap(count, cap) {
  return count >= cap;
}
