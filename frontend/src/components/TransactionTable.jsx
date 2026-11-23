import React, { useMemo, useState } from "react";
import { Search, CheckCircle2 } from "lucide-react";
import {
  VALID_CATEGORIES,
  formatShortDate,
  formatSignedCurrency,
} from "../utils/formatters";

const KIND_STYLES = {
  income: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  expense: "bg-slate-800 text-slate-300 border-slate-700",
  refund: "bg-cyan-500/15 text-cyan-300 border-cyan-500/30",
  reversal: "bg-cyan-500/15 text-cyan-300 border-cyan-500/30",
  transfer: "bg-violet-500/15 text-violet-300 border-violet-500/30",
};

export default function TransactionTable({
  transactions = [],
  onUpdateCategory,
  loading = false,
}) {
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("All");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [updatingId, setUpdatingId] = useState(null);

  const availableCategories = useMemo(
    () => ["All", ...Array.from(new Set(transactions.map((t) => t.category)))],
    [transactions]
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return transactions.filter((tx) => {
      if (categoryFilter !== "All" && tx.category !== categoryFilter) return false;
      if (startDate && tx.date < startDate) return false;
      if (endDate && tx.date > endDate) return false;
      if (
        q &&
        !tx.merchant.toLowerCase().includes(q) &&
        !tx.description.toLowerCase().includes(q)
      ) {
        return false;
      }
      return true;
    });
  }, [transactions, search, categoryFilter, startDate, endDate]);

  const handleCategoryChange = async (txId, newCategory) => {
    setUpdatingId(txId);
    try {
      await onUpdateCategory(txId, newCategory);
    } finally {
      setUpdatingId(null);
    }
  };

  return (
    <div className="rounded-2xl bg-slate-900/70 border border-slate-800 p-5">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 mb-4">
        <div>
          <h2 className="text-base font-semibold text-white">Transactions</h2>
          <p className="text-xs text-slate-400">
            Showing {filtered.length} of {transactions.length} PII-scrubbed records
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search className="h-3.5 w-3.5 text-slate-500 absolute left-3 top-2.5" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search merchant or narration..."
              className="pl-8 pr-3 py-1.5 text-xs rounded-xl bg-slate-950 border border-slate-800 text-slate-200 focus:outline-none focus:border-emerald-500 w-52"
            />
          </div>

          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="px-2.5 py-1.5 text-xs rounded-xl bg-slate-950 border border-slate-800 text-slate-200 focus:outline-none focus:border-emerald-500"
          >
            {availableCategories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>

          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            aria-label="Start date"
            className="px-2.5 py-1.5 text-xs rounded-xl bg-slate-950 border border-slate-800 text-slate-200 focus:outline-none focus:border-emerald-500"
          />
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            aria-label="End date"
            className="px-2.5 py-1.5 text-xs rounded-xl bg-slate-950 border border-slate-800 text-slate-200 focus:outline-none focus:border-emerald-500"
          />
        </div>
      </div>

      {loading ? (
        <div className="py-10 text-center text-xs text-slate-400 animate-pulse">
          Loading verified transactions...
        </div>
      ) : filtered.length === 0 ? (
        <div className="py-10 text-center text-sm text-slate-500">
          No transactions match your current filters.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-800 text-[11px] uppercase tracking-wider text-slate-400">
                <th className="py-3 px-3">Date</th>
                <th className="py-3 px-3">Merchant &amp; Description</th>
                <th className="py-3 px-3">Type</th>
                <th className="py-3 px-3">Category (Editable)</th>
                <th className="py-3 px-3 text-right">Amount</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-xs">
              {filtered.map((tx) => (
                <tr key={tx.id} className="hover:bg-slate-800/30 transition">
                  <td className="py-3 px-3 text-slate-400 whitespace-nowrap">
                    {formatShortDate(tx.date)}
                  </td>
                  <td className="py-3 px-3">
                    <div className="font-medium text-slate-100">{tx.merchant}</div>
                    <div className="text-[11px] text-slate-500 truncate max-w-xs" title={tx.description}>
                      {tx.description}
                    </div>
                  </td>
                  <td className="py-3 px-3 whitespace-nowrap">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full border text-[10px] font-medium capitalize ${
                        KIND_STYLES[tx.tx_kind] || KIND_STYLES.expense
                      }`}
                    >
                      {tx.tx_kind}
                    </span>
                  </td>
                  <td className="py-3 px-3 whitespace-nowrap">
                    <div className="flex items-center gap-1.5">
                      <select
                        value={tx.category}
                        disabled={updatingId === tx.id}
                        onChange={(e) => handleCategoryChange(tx.id, e.target.value)}
                        className="rounded-lg bg-slate-950 border border-slate-700 px-2 py-1 text-xs text-slate-200 focus:outline-none focus:border-emerald-500 disabled:opacity-50"
                      >
                        {VALID_CATEGORIES.map((cat) => (
                          <option key={cat} value={cat}>
                            {cat}
                          </option>
                        ))}
                      </select>
                      {tx.user_corrected && (
                        <span title="User-verified category">
                          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                        </span>
                      )}
                    </div>
                  </td>
                  <td
                    className={`py-3 px-3 text-right font-semibold whitespace-nowrap ${
                      tx.amount >= 0 ? "text-emerald-400" : "text-slate-100"
                    }`}
                  >
                    {formatSignedCurrency(tx.amount)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
