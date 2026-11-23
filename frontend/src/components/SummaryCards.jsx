import React from "react";
import {
  Landmark,
  ArrowDownLeft,
  ArrowUpRight,
  PiggyBank,
  TrendingUp,
} from "lucide-react";
import { formatCurrency } from "../utils/formatters";

export default function SummaryCards({ summary, loading = false }) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <div
            key={i}
            className="h-28 rounded-2xl bg-slate-900/60 border border-slate-800 animate-pulse"
          />
        ))}
      </div>
    );
  }

  const hasBalance = summary?.current_balance !== null && summary?.current_balance !== undefined;
  const momPct = summary?.mom_expense_change_pct;

  const cards = [
    {
      label: hasBalance ? "Current Balance" : "Net Cash Flow",
      value: formatCurrency(hasBalance ? summary.current_balance : summary?.net_cash_flow),
      sub: hasBalance ? "From latest statement balance" : "Income minus net expenses",
      icon: Landmark,
      accent: "text-cyan-400 bg-cyan-500/10 border-cyan-500/20",
    },
    {
      label: "Total Income",
      value: formatCurrency(summary?.total_income),
      sub: "Excludes refunds & transfers",
      icon: ArrowDownLeft,
      accent: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
    },
    {
      label: "Total Expenses",
      value: formatCurrency(summary?.total_expenses),
      sub:
        summary?.total_refunds > 0
          ? `Net after ${formatCurrency(summary.total_refunds)} refunds`
          : `${summary?.transaction_count ?? 0} total entries`,
      icon: ArrowUpRight,
      accent: "text-rose-400 bg-rose-500/10 border-rose-500/20",
    },
    {
      label: "Net Savings",
      value: formatCurrency(summary?.savings_amount),
      sub:
        (summary?.savings_amount ?? 0) >= 0
          ? "Positive monthly surplus"
          : "Spending exceeded income",
      icon: PiggyBank,
      accent: "text-sky-400 bg-sky-500/10 border-sky-500/20",
    },
    {
      label: "Savings Rate",
      value: `${summary?.savings_rate_pct ?? 0}%`,
      sub:
        momPct !== null && momPct !== undefined
          ? `MoM spend: ${momPct > 0 ? "+" : ""}${momPct}%`
          : "Python Decimal verified",
      icon: TrendingUp,
      accent: "text-violet-400 bg-violet-500/10 border-violet-500/20",
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4">
      {cards.map((card) => {
        const Icon = card.icon;
        return (
          <div
            key={card.label}
            className="rounded-2xl bg-slate-900/70 border border-slate-800/90 p-4 flex items-start justify-between hover:border-slate-700 transition"
          >
            <div className="min-w-0">
              <p className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
                {card.label}
              </p>
              <p className="mt-2 text-xl font-bold text-white truncate">{card.value}</p>
              <p className="mt-1 text-[11px] text-slate-500 truncate">{card.sub}</p>
            </div>
            <div className={`p-2 rounded-xl border shrink-0 ${card.accent}`}>
              <Icon className="h-4 w-4" />
            </div>
          </div>
        );
      })}
    </div>
  );
}
