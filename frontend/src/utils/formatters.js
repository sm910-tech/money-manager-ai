export const VALID_CATEGORIES = [
  "Food & Dining",
  "Groceries",
  "Transport",
  "Utilities",
  "Housing & Rent",
  "Shopping",
  "Entertainment",
  "Health",
  "Education",
  "Subscriptions",
  "Transfers",
  "Refunds",
  "Income",
  "Other",
];

export const BUDGETABLE_CATEGORIES = [
  "Food & Dining",
  "Groceries",
  "Transport",
  "Utilities",
  "Housing & Rent",
  "Shopping",
  "Subscriptions",
  "Entertainment",
  "Health",
  "Education",
  "Other",
];

export function formatCurrency(amount, { showDecimals = false } = {}) {
  const num = Number(amount ?? 0);
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: showDecimals ? 2 : 0,
    maximumFractionDigits: showDecimals ? 2 : 0,
  }).format(Number.isFinite(num) ? num : 0);
}

export function formatSignedCurrency(amount) {
  const num = Number(amount ?? 0);
  const prefix = num > 0 ? "+" : num < 0 ? "-" : "";
  return `${prefix}${formatCurrency(Math.abs(num), { showDecimals: true })}`;
}

export function formatMonthLabel(ym) {
  if (!ym || !/^\d{4}-\d{2}$/.test(ym)) return ym || "";
  const [year, month] = ym.split("-");
  const date = new Date(Number(year), Number(month) - 1, 1);
  return date.toLocaleDateString("en-IN", { month: "short", year: "numeric" });
}

export function formatShortDate(isoDate) {
  if (!isoDate) return "";
  const dt = new Date(`${isoDate}T00:00:00`);
  if (Number.isNaN(dt.getTime())) return isoDate;
  return dt.toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export function getCurrentMonthKey() {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  return `${y}-${m}`;
}
