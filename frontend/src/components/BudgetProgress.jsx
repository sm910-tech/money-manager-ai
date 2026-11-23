import React, { useEffect, useState } from "react";
import { Pencil, Save, X, Plus } from "lucide-react";
import { BUDGETABLE_CATEGORIES, formatCurrency, formatMonthLabel } from "../utils/formatters";

export default function BudgetProgress({
  budgets = [],
  selectedMonth,
  onMonthChange,
  onSaveBudgets,
  saving = false,
  isDemoMode = false,
}) {
  const [editing, setEditing] = useState(false);
  const [draftLimits, setDraftLimits] = useState({});
  const [newCategory, setNewCategory] = useState("");
  const [newLimit, setNewLimit] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const map = {};
    (budgets || []).forEach((b) => {
      map[b.category] = b.limit;
    });
    setDraftLimits(map);
  }, [budgets]);

  const availableToAdd = BUDGETABLE_CATEGORIES.filter((c) => !(c in draftLimits));

  const handleAddCategory = () => {
    const numeric = Number(newLimit);
    if (!newCategory || !Number.isFinite(numeric) || numeric < 0) {
      setError("Select a category and enter a valid non-negative amount.");
      return;
    }
    setDraftLimits((prev) => ({ ...prev, [newCategory]: numeric }));
    setNewCategory("");
    setNewLimit("");
    setError("");
  };

  const handleSave = async () => {
    const cleaned = {};
    for (const [cat, val] of Object.entries(draftLimits)) {
      const n = Number(val);
      if (!Number.isFinite(n) || n < 0) {
        setError(`Invalid limit for ${cat}.`);
        return;
      }
      cleaned[cat] = n;
    }
    setError("");
    try {
      await onSaveBudgets(selectedMonth, cleaned);
      setEditing(false);
    } catch (err) {
      setError(err.message || "Failed to save budgets.");
    }
  };

  return (
    <div className="rounded-2xl bg-slate-900/70 border border-slate-800 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div>
          <h2 className="text-base font-semibold text-white">Monthly Budgets</h2>
          <p className="text-xs text-slate-400">
            {formatMonthLabel(selectedMonth)} • Spent vs. remaining allocation
          </p>
        </div>

        <div className="flex items-center gap-2">
          <input
            type="month"
            value={selectedMonth}
            onChange={(e) => onMonthChange(e.target.value)}
            className="rounded-xl bg-slate-950 border border-slate-800 px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
          />
          {!editing ? (
            <button
              onClick={() => setEditing(true)}
              className="inline-flex items-center gap-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 px-3 py-1.5 text-xs font-medium text-slate-200"
            >
              <Pencil className="h-3.5 w-3.5" />
              Edit Limits
            </button>
          ) : (
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setEditing(false)}
                className="inline-flex items-center gap-1 rounded-xl bg-slate-800 hover:bg-slate-700 px-2.5 py-1.5 text-xs text-slate-300"
              >
                <X className="h-3.5 w-3.5" />
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="inline-flex items-center gap-1 rounded-xl bg-emerald-500 hover:bg-emerald-400 px-3 py-1.5 text-xs font-semibold text-slate-950 disabled:opacity-50"
              >
                <Save className="h-3.5 w-3.5" />
                {saving ? "Saving..." : "Save"}
              </button>
            </div>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-3 rounded-xl bg-rose-500/10 border border-rose-500/30 p-2.5 text-xs text-rose-300">
          {error}
        </div>
      )}

      {editing ? (
        <div className="space-y-3">
          {isDemoMode && (
            <p className="text-[11px] text-amber-300">
              Demo preview: budget changes stay local in memory and are never saved to Firestore.
            </p>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {Object.entries(draftLimits).map(([cat, limit]) => (
              <div key={cat} className="flex items-center justify-between gap-2 rounded-xl bg-slate-950 border border-slate-800 px-3 py-2">
                <label className="text-xs font-medium text-slate-200 truncate">{cat}</label>
                <input
                  type="number"
                  min="0"
                  step="100"
                  value={limit}
                  onChange={(e) =>
                    setDraftLimits((prev) => ({ ...prev, [cat]: e.target.value }))
                  }
                  className="w-28 rounded-lg bg-slate-900 border border-slate-700 px-2 py-1 text-right text-xs text-white focus:outline-none focus:border-emerald-500"
                />
              </div>
            ))}
          </div>

          {availableToAdd.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-800">
              <select
                value={newCategory}
                onChange={(e) => setNewCategory(e.target.value)}
                className="rounded-xl bg-slate-950 border border-slate-800 px-2.5 py-1.5 text-xs text-slate-200"
              >
                <option value="">+ Add Category...</option>
                {availableToAdd.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
              <input
                type="number"
                min="0"
                placeholder="Limit (₹)"
                value={newLimit}
                onChange={(e) => setNewLimit(e.target.value)}
                className="w-28 rounded-xl bg-slate-950 border border-slate-800 px-2.5 py-1.5 text-xs text-slate-200"
              />
              <button
                type="button"
                onClick={handleAddCategory}
                className="inline-flex items-center gap-1 rounded-xl bg-slate-800 hover:bg-slate-700 px-3 py-1.5 text-xs text-emerald-400 font-medium"
              >
                <Plus className="h-3.5 w-3.5" />
                Add
              </button>
            </div>
          )}
        </div>
      ) : budgets.length === 0 ? (
        <p className="text-xs text-slate-500 py-6 text-center">
          No budgets configured yet. Click Edit Limits to create monthly targets.
        </p>
      ) : (
        <div className="space-y-4">
          {budgets.map((b) => {
            const barColor =
              b.status === "exceeded"
                ? "bg-rose-500"
                : b.status === "warning"
                ? "bg-amber-400"
                : "bg-emerald-400";
            const badgeStyle =
              b.status === "exceeded"
                ? "bg-rose-500/15 text-rose-300 border-rose-500/30"
                : b.status === "warning"
                ? "bg-amber-500/15 text-amber-300 border-amber-500/30"
                : "bg-emerald-500/15 text-emerald-300 border-emerald-500/30";

            return (
              <div key={b.category}>
                <div className="flex items-center justify-between text-xs mb-1.5 gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="font-medium text-slate-200 truncate">{b.category}</span>
                    <span className={`px-2 py-0.5 rounded-full border text-[10px] font-medium ${badgeStyle}`}>
                      {b.utilization_pct}%
                    </span>
                  </div>
                  <span className="text-slate-400 shrink-0">
                    <strong className="text-slate-100">{formatCurrency(b.spent)}</strong> /{" "}
                    {formatCurrency(b.limit)}
                  </span>
                </div>
                <div className="h-2 w-full rounded-full bg-slate-800 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-300 ${barColor}`}
                    style={{ width: `${Math.min(b.utilization_pct, 100)}%` }}
                  />
                </div>
                <div className="mt-1 flex justify-between text-[11px] text-slate-500">
                  <span>
                    {b.remaining >= 0
                      ? `${formatCurrency(b.remaining)} remaining`
                      : `Over budget by ${formatCurrency(Math.abs(b.remaining))}`}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
