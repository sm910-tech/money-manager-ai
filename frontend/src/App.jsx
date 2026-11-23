import React, { useCallback, useEffect, useState } from "react";
import { Menu, LogIn, LogOut, FlaskConical, AlertTriangle, RefreshCw } from "lucide-react";

import Sidebar from "./components/Sidebar";
import SummaryCards from "./components/SummaryCards";
import SpendingChart from "./components/SpendingChart";
import BudgetProgress from "./components/BudgetProgress";
import TransactionTable from "./components/TransactionTable";
import CsvUploadModal from "./components/CsvUploadModal";
import AiAssistantPanel from "./components/AiAssistantPanel";

import {
  DEMO_MONTH,
  DEMO_MONTHLY,
  DEMO_SUMMARY,
  DEMO_TRANSACTIONS,
} from "./data/demoData";
import {
  checkBackendHealth,
  fetchAnalyticsSummary,
  fetchBudgets,
  fetchMonthlyAnalytics,
  fetchTransactions,
  patchTransaction,
  updateBudgets,
} from "./services/api";
import {
  isFirebaseConfigured,
  loginWithGoogle,
  logoutUser,
  subscribeToAuth,
} from "./services/firebase";
import { getCurrentMonthKey } from "./utils/formatters";

const EMPTY_SUMMARY = {
  total_income: 0,
  total_expenses: 0,
  gross_expenses: 0,
  total_refunds: 0,
  net_cash_flow: 0,
  savings_amount: 0,
  savings_rate_pct: 0,
  current_balance: null,
  transaction_count: 0,
  category_breakdown: [],
  budgets: [],
  top_merchants: [],
  recurring_transactions: [],
};

export default function App() {
  const [activeTab, setActiveTab] = useState("overview");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);

  const [user, setUser] = useState(null);
  const [authReady, setAuthReady] = useState(false);
  const [backendHealth, setBackendHealth] = useState(null);

  const [selectedMonth, setSelectedMonth] = useState(DEMO_MONTH);
  const [transactions, setTransactions] = useState([]);
  const [summary, setSummary] = useState(EMPTY_SUMMARY);
  const [monthly, setMonthly] = useState([]);
  const [budgetStatuses, setBudgetStatuses] = useState([]);

  const [loadingData, setLoadingData] = useState(false);
  const [savingBudget, setSavingBudget] = useState(false);
  const [banner, setBanner] = useState(null);
  const [errorBanner, setErrorBanner] = useState("");

  const isAuthenticated = Boolean(user);
  const isDemoMode = !isAuthenticated;

  useEffect(() => {
    checkBackendHealth()
      .then((h) => setBackendHealth(h))
      .catch(() => setBackendHealth({ status: "offline" }));

    const unsub = subscribeToAuth((fbUser) => {
      setUser(fbUser);
      setAuthReady(true);
      if (fbUser) {
        // Immediately clear any synthetic demo records when authenticated
        setTransactions([]);
        setSummary(EMPTY_SUMMARY);
        setMonthly([]);
        setBudgetStatuses([]);
        setSelectedMonth(getCurrentMonthKey());
      } else {
        setSelectedMonth(DEMO_MONTH);
      }
    });
    return unsub;
  }, []);

  const loadAuthenticatedDashboard = useCallback(
    async (monthKey) => {
      if (!user) return;
      setLoadingData(true);
      setErrorBanner("");
      try {
        const [txRes, sumRes, monRes, budRes] = await Promise.all([
          fetchTransactions({ limit: 500 }),
          fetchAnalyticsSummary(),
          fetchMonthlyAnalytics(),
          fetchBudgets(monthKey),
        ]);
        setTransactions(txRes.transactions || []);
        setSummary(sumRes || EMPTY_SUMMARY);
        setMonthly(monRes.months || []);
        setBudgetStatuses(budRes.statuses || []);
      } catch (err) {
        setErrorBanner(err.message || "Failed to load your financial records from the server.");
      } finally {
        setLoadingData(false);
      }
    },
    [user]
  );

  useEffect(() => {
    if (!authReady) return;
    if (isAuthenticated) {
      loadAuthenticatedDashboard(selectedMonth);
    } else {
      // Strictly isolated synthetic demo data for unauthenticated exploration
      setTransactions(DEMO_TRANSACTIONS);
      setSummary(DEMO_SUMMARY);
      setMonthly(DEMO_MONTHLY.months);
      setBudgetStatuses(DEMO_SUMMARY.budgets);
      setErrorBanner("");
    }
  }, [authReady, isAuthenticated, selectedMonth, loadAuthenticatedDashboard]);

  const handleUploadSuccess = async (result) => {
    setBanner(
      `Imported ${result.imported_count} transaction(s) from "${result.filename}" ` +
        `[${result.detected_bank.toUpperCase()}] • ${result.duplicate_count} duplicate(s) skipped` +
        (result.ai_categorized_count ? ` • ${result.ai_categorized_count} AI-categorized` : "")
    );
    await loadAuthenticatedDashboard(selectedMonth);
  };

  const handleUpdateCategory = async (txId, newCategory) => {
    if (isDemoMode) {
      setTransactions((prev) =>
        prev.map((t) =>
          t.id === txId
            ? { ...t, category: newCategory, user_corrected: true, category_source: "user" }
            : t
        )
      );
      return;
    }
    try {
      await patchTransaction(txId, { category: newCategory });
      await loadAuthenticatedDashboard(selectedMonth);
    } catch (err) {
      setErrorBanner(err.message || "Failed to update transaction category.");
    }
  };

  const handleSaveBudgets = async (monthKey, limits) => {
    setSavingBudget(true);
    try {
      if (isDemoMode) {
        const updated = Object.entries(limits).map(([cat, limit]) => {
          const existing = budgetStatuses.find((b) => b.category === cat);
          const spent = existing ? existing.spent : 0;
          const remaining = limit - spent;
          const util = limit > 0 ? Math.round((spent / limit) * 1000) / 10 : 0;
          const status = util > 100 ? "exceeded" : util >= 80 ? "warning" : "on_track";
          return { category: cat, limit, spent, remaining, utilization_pct: util, status };
        });
        setBudgetStatuses(updated);
        return;
      }
      const res = await updateBudgets(monthKey, limits);
      setBudgetStatuses(res.statuses || []);
      await loadAuthenticatedDashboard(monthKey);
    } finally {
      setSavingBudget(false);
    }
  };

  const handleSignIn = async () => {
    setErrorBanner("");
    try {
      await loginWithGoogle();
    } catch (err) {
      setErrorBanner(err.message || "Google sign-in failed.");
    }
  };

  return (
    <div className="min-h-screen flex bg-slate-950 text-slate-100">
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onOpenUpload={() => setUploadOpen(true)}
        mobileOpen={mobileOpen}
        setMobileOpen={setMobileOpen}
        backendHealth={backendHealth}
        isDemoMode={isDemoMode}
      />

      <div className="flex-1 flex flex-col min-w-0">
        <header className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-800/80 bg-slate-950/90 backdrop-blur px-4 lg:px-8 py-3.5">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileOpen(true)}
              className="lg:hidden p-2 rounded-lg text-slate-400 hover:bg-slate-800 hover:text-white"
              aria-label="Open navigation"
            >
              <Menu className="h-5 w-5" />
            </button>
            <h2 className="text-base font-semibold text-white capitalize">
              {activeTab === "overview" ? "Financial Overview" : activeTab}
            </h2>
          </div>

          <div className="flex items-center gap-2.5">
            {isDemoMode && (
              <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full bg-amber-500/10 border border-amber-500/30 px-3 py-1 text-xs font-medium text-amber-300">
                <FlaskConical className="h-3.5 w-3.5" />
                Synthetic Demo Mode
              </span>
            )}

            {isAuthenticated && (
              <button
                onClick={() => loadAuthenticatedDashboard(selectedMonth)}
                className="p-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300"
                title="Refresh data"
              >
                <RefreshCw className={`h-4 w-4 ${loadingData ? "animate-spin" : ""}`} />
              </button>
            )}

            {isAuthenticated ? (
              <button
                onClick={logoutUser}
                className="inline-flex items-center gap-2 rounded-xl bg-slate-800 hover:bg-slate-700 px-3 py-1.5 text-xs font-medium text-slate-200"
              >
                <LogOut className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">{user.displayName || user.email}</span>
                <span>Sign Out</span>
              </button>
            ) : (
              <button
                onClick={handleSignIn}
                className="inline-flex items-center gap-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 px-3.5 py-1.5 text-xs font-semibold text-slate-950"
              >
                <LogIn className="h-3.5 w-3.5" />
                {isFirebaseConfigured ? "Sign In with Google" : "Configure Firebase to Sign In"}
              </button>
            )}
          </div>
        </header>

        <main className="flex-1 p-4 lg:p-8 max-w-7xl w-full mx-auto space-y-6">
          {isDemoMode && (
            <div className="rounded-2xl bg-amber-500/10 border border-amber-500/25 p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <p className="text-xs text-amber-200 leading-relaxed">
                <strong>Synthetic Demo Mode Active:</strong> You are viewing isolated, synthetic sample records. Demo data is never mixed with authenticated user accounts or written to Firestore. Sign in with Google to upload your own bank CSV statements.
              </p>
              {isFirebaseConfigured && (
                <button
                  onClick={handleSignIn}
                  className="shrink-0 rounded-xl bg-amber-400 hover:bg-amber-300 text-slate-950 font-semibold px-3.5 py-1.5 text-xs"
                >
                  Sign In Now
                </button>
              )}
            </div>
          )}

          {banner && (
            <div className="rounded-2xl bg-emerald-500/10 border border-emerald-500/30 p-3.5 text-xs text-emerald-300 flex items-center justify-between">
              <span>{banner}</span>
              <button onClick={() => setBanner(null)} className="text-emerald-400 hover:text-white ml-4">
                Dismiss
              </button>
            </div>
          )}

          {errorBanner && (
            <div className="rounded-2xl bg-rose-500/10 border border-rose-500/30 p-3.5 text-xs text-rose-300 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              <span>{errorBanner}</span>
            </div>
          )}

          <SummaryCards summary={summary} loading={loadingData} />

          {activeTab === "overview" && (
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
              <div className="xl:col-span-2 space-y-6">
                <SpendingChart
                  categories={summary.category_breakdown}
                  monthly={monthly}
                  topMerchants={summary.top_merchants}
                  recurring={summary.recurring_transactions}
                />
                <BudgetProgress
                  budgets={budgetStatuses}
                  selectedMonth={selectedMonth}
                  onMonthChange={setSelectedMonth}
                  onSaveBudgets={handleSaveBudgets}
                  saving={savingBudget}
                  isDemoMode={isDemoMode}
                />
                <TransactionTable
                  transactions={transactions}
                  onUpdateCategory={handleUpdateCategory}
                  loading={loadingData}
                />
              </div>
              <div>
                <AiAssistantPanel
                  isAuthenticated={isAuthenticated}
                  selectedMonth={isAuthenticated ? null : selectedMonth}
                />
              </div>
            </div>
          )}

          {activeTab === "transactions" && (
            <TransactionTable
              transactions={transactions}
              onUpdateCategory={handleUpdateCategory}
              loading={loadingData}
            />
          )}

          {activeTab === "budgets" && (
            <div className="space-y-6">
              <BudgetProgress
                budgets={budgetStatuses}
                selectedMonth={selectedMonth}
                onMonthChange={setSelectedMonth}
                onSaveBudgets={handleSaveBudgets}
                saving={savingBudget}
                isDemoMode={isDemoMode}
              />
              <SpendingChart
                categories={summary.category_breakdown}
                monthly={monthly}
                topMerchants={summary.top_merchants}
                recurring={summary.recurring_transactions}
              />
            </div>
          )}

          {activeTab === "assistant" && (
            <div className="max-w-3xl mx-auto">
              <AiAssistantPanel
                isAuthenticated={isAuthenticated}
                selectedMonth={isAuthenticated ? null : selectedMonth}
              />
            </div>
          )}
        </main>
      </div>

      <CsvUploadModal
        isOpen={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onUploadSuccess={handleUploadSuccess}
        isAuthenticated={isAuthenticated}
      />
    </div>
  );
}
