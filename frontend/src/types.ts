export interface EventSummary {
  id: string;
  name: string;
  start_date: string | null;
  image: string | null;
  url: string | null;
  venue: { name: string } | null;
  category: { segment: string | null } | null;
  offers: { price_min: number | null; price_max: number | null; currency: string | null }[];
}

export function formatPrice(offers: EventSummary["offers"]): string | null {
  const offer = offers[0];
  if (!offer || offer.price_min == null) return null;
  const currency = offer.currency || "USD";
  return `${offer.price_min} ${currency}`;
}

export function formatDate(iso: string | null): string | null {
  if (!iso) return null;
  return new Date(iso).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

const CATEGORY_TINTS: Record<string, string> = {
  music: "#7b6bf0",
  sports: "#2f6bed",
  "arts & theatre": "#e0794f",
  film: "#2fa88e",
};

export function categoryTint(segment: string | null | undefined): string {
  if (!segment) return "#7b6bf0";
  return CATEGORY_TINTS[segment.toLowerCase()] || "#7b6bf0";
}
