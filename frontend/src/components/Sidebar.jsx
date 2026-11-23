import React from "react";
import {
  LayoutDashboard,
  ArrowLeftRight,
  PieChart,
  Bot,
  Upload,
  ShieldCheck,
  X,
} from "lucide-react";

const NAV_ITEMS = [
  { id: "overview", label: "Dashboard Overview", icon: LayoutDashboard },
  { id: "transactions", label: "Transactions", icon: ArrowLeftRight },
  { id: "budgets", label: "Budgets & Insights", icon: PieChart },
  { id: "assistant", label: "AI Copilot", icon: Bot },
];

export default function Sidebar({
  activeTab,
  setActiveTab,
  onOpenUpload,
  mobileOpen,
  setMobileOpen,
  backendHealth,
  isDemoMode,
}) {
  const isOnline = backendHealth?.status === "ok";

  const content = (
    <div className="flex h-full flex-col justify-between bg-slate-900/95 border-r border-slate-800/80 p-4 w-64">
      <div>
        <div className="flex items-center justify-between px-2 py-3 mb-6">
          <div className="flex items-center gap-2.5">
            <div className="h-9 w-9 rounded-xl bg-emerald-500/15 border border-emerald-500/40 flex items-center justify-center text-emerald-400 font-bold text-lg">
              ₹
            </div>
            <div>
              <h1 className="text-base font-semibold tracking-tight text-white">Money Manager</h1>
              <p className="text-[11px] text-slate-400">FinTech AI Assistant</p>
            </div>
          </div>
          <button
            onClick={() => setMobileOpen(false)}
            className="lg:hidden text-slate-400 hover:text-white p-1"
            aria-label="Close navigation"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <button
          onClick={() => {
            onOpenUpload();
            setMobileOpen(false);
          }}
          className="w-full mb-6 flex items-center justify-center gap-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-semibold py-2.5 px-4 text-sm transition shadow-lg shadow-emerald-500/15"
        >
          <Upload className="h-4 w-4" />
          Upload Bank CSV
        </button>

        <nav className="space-y-1">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  setActiveTab(item.id);
                  setMobileOpen(false);
                }}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition ${
                  active
                    ? "bg-slate-800 text-emerald-400 border border-slate-700/80"
                    : "text-slate-400 hover:text-slate-100 hover:bg-slate-800/50"
                }`}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </button>
            );
          })}
        </nav>
      </div>

      <div className="space-y-3 border-t border-slate-800 pt-4 text-xs">
        <div className="rounded-xl bg-slate-950/90 border border-slate-800 p-3">
          <div className="flex items-center gap-2 text-emerald-400 font-medium mb-1">
            <ShieldCheck className="h-4 w-4 shrink-0" />
            <span>Zero-Credential Security</span>
          </div>
          <p className="text-slate-400 leading-relaxed text-[11px]">
            CSV-only ingestion. Never requests bank passwords, CVVs, or UPI PINs.
          </p>
        </div>

        <div className="space-y-1.5 px-2 text-[11px] text-slate-400">
          <div className="flex items-center justify-between">
            <span>Backend API</span>
            <span className="flex items-center gap-1.5 font-medium text-slate-300">
              <span className={`h-2 w-2 rounded-full ${isOnline ? "bg-emerald-400" : "bg-rose-400"}`} />
              {isOnline ? "Connected" : "Offline"}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span>Data Mode</span>
            <span className={isDemoMode ? "text-amber-300 font-medium" : "text-emerald-400 font-medium"}>
              {isDemoMode ? "Synthetic Demo" : "Authenticated"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <>
      <aside className="hidden lg:block shrink-0">{content}</aside>
      {mobileOpen && (
        <div className="fixed inset-0 z-50 flex lg:hidden">
          <div
            className="fixed inset-0 bg-black/65 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
          />
          <div className="relative z-10">{content}</div>
        </div>
      )}
    </>
  );
}
