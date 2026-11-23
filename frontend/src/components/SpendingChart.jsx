import React from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { Repeat, Store } from "lucide-react";
import { formatCurrency, formatMonthLabel } from "../utils/formatters";

const PIE_COLORS = [
  "#10b981",
  "#38bdf8",
  "#8b5cf6",
  "#f59e0b",
  "#f43f5e",
  "#14b8a6",
  "#6366f1",
  "#ec4899",
];

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl bg-slate-950/95 border border-slate-700 px-3 py-2 text-xs shadow-xl">
      {label && <p className="font-semibold text-slate-200 mb-1">{label}</p>}
      {payload.map((entry, idx) => (
        <p key={idx} className="flex items-center justify-between gap-4" style={{ color: entry.color }}>
          <span>{entry.name}:</span>
          <span className="font-semibold">{formatCurrency(entry.value)}</span>
        </p>
      ))}
    </div>
  );
}

export default function SpendingChart({
  categories = [],
  monthly = [],
  topMerchants = [],
  recurring = [],
}) {
  const monthlyChartData = (monthly || []).map((m) => ({
    ...m,
    label: formatMonthLabel(m.month),
  }));

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <div className="rounded-2xl bg-slate-900/70 border border-slate-800 p-5">
          <div className="mb-4">
            <h2 className="text-base font-semibold text-white">Monthly Cash Flow</h2>
            <p className="text-xs text-slate-400">Income vs. net expenses over time</p>
          </div>
          {monthlyChartData.length === 0 ? (
            <div className="h-64 flex items-center justify-center text-sm text-slate-500">
              Upload a bank statement to visualize monthly spending trends.
            </div>
          ) : (
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={monthlyChartData} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="label" tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="income" name="Income" fill="#10b981" radius={[6, 6, 0, 0]} />
                  <Bar dataKey="expenses" name="Expenses" fill="#f43f5e" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        <div className="rounded-2xl bg-slate-900/70 border border-slate-800 p-5">
          <div className="mb-4">
            <h2 className="text-base font-semibold text-white">Category Breakdown</h2>
            <p className="text-xs text-slate-400">Share of gross expenditure by category</p>
          </div>

          {categories.length === 0 ? (
            <div className="h-64 flex items-center justify-center text-sm text-slate-500">
              No categorized expenses available yet.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 items-center">
              <div className="h-56 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={categories}
                      dataKey="total"
                      nameKey="category"
                      cx="50%"
                      cy="50%"
                      innerRadius={52}
                      outerRadius={82}
                      paddingAngle={3}
                    >
                      {categories.map((entry, idx) => (
                        <Cell key={entry.category} fill={PIE_COLORS[idx % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip content={<CustomTooltip />} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                {categories.map((item, idx) => (
                  <div key={item.category} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2 min-w-0">
                      <span
                        className="h-2.5 w-2.5 rounded-full shrink-0"
                        style={{ backgroundColor: PIE_COLORS[idx % PIE_COLORS.length] }}
                      />
                      <span className="text-slate-200 truncate">{item.category}</span>
                    </div>
                    <span className="text-slate-400 shrink-0 ml-2">
                      {formatCurrency(item.total)} ({item.percentage}%)
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="rounded-2xl bg-slate-900/70 border border-slate-800 p-5">
          <div className="flex items-center gap-2 mb-3">
            <Store className="h-4 w-4 text-sky-400" />
            <h3 className="text-sm font-semibold text-white">Top Spending Merchants</h3>
          </div>
          {topMerchants.length === 0 ? (
            <p className="text-xs text-slate-500">No merchant data yet.</p>
          ) : (
            <div className="space-y-2.5">
              {topMerchants.slice(0, 5).map((m) => (
                <div key={m.merchant} className="flex items-center justify-between text-xs border-b border-slate-800/60 pb-2 last:border-none last:pb-0">
                  <div>
                    <p className="font-medium text-slate-200">{m.merchant}</p>
                    <p className="text-[11px] text-slate-500">
                      {m.category} • {m.transaction_count} txn{m.transaction_count > 1 ? "s" : ""}
                    </p>
                  </div>
                  <span className="font-semibold text-slate-100">{formatCurrency(m.total_spent)}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-2xl bg-slate-900/70 border border-slate-800 p-5">
          <div className="flex items-center gap-2 mb-3">
            <Repeat className="h-4 w-4 text-amber-400" />
            <h3 className="text-sm font-semibold text-white">Detected Recurring Expenses</h3>
          </div>
          {recurring.length === 0 ? (
            <p className="text-xs text-slate-500">
              Upload statements spanning 2+ months to detect subscriptions & recurring bills.
            </p>
          ) : (
            <div className="space-y-2.5">
              {recurring.slice(0, 5).map((r) => (
                <div key={r.merchant} className="flex items-center justify-between text-xs border-b border-slate-800/60 pb-2 last:border-none last:pb-0">
                  <div>
                    <p className="font-medium text-slate-200">{r.merchant}</p>
                    <p className="text-[11px] text-slate-500">
                      {r.category} • {r.occurrences} occurrences ({r.frequency})
                    </p>
                  </div>
                  <span className="font-semibold text-amber-300">
                    ~{formatCurrency(r.average_amount)}/mo
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
