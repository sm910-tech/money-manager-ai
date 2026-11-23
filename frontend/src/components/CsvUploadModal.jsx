import React, { useState } from "react";
import {
  Upload,
  X,
  FileSpreadsheet,
  AlertCircle,
  ShieldCheck,
  SlidersHorizontal,
} from "lucide-react";
import { uploadCsvStatement } from "../services/api";

export default function CsvUploadModal({
  isOpen,
  onClose,
  onUploadSuccess,
  isAuthenticated,
}) {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [ambiguousInfo, setAmbiguousInfo] = useState(null);
  const [mapping, setMapping] = useState({
    date: "",
    description: "",
    amount: "",
    debit: "",
    credit: "",
    tx_type: "",
    balance: "",
  });

  if (!isOpen) return null;

  const resetAndClose = () => {
    setFile(null);
    setError("");
    setAmbiguousInfo(null);
    onClose();
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!isAuthenticated) {
      setError("Sign in with Google first to upload and persist personal bank statements.");
      return;
    }
    if (!file) {
      setError("Please select a .csv statement file first.");
      return;
    }

    setLoading(true);
    setError("");

    const activeMapping = ambiguousInfo
      ? Object.fromEntries(
          Object.entries(mapping).filter(([, v]) => v && v.trim() !== "")
        )
      : null;

    try {
      const result = await uploadCsvStatement(file, activeMapping);
      onUploadSuccess(result);
      resetAndClose();
    } catch (err) {
      if (err.status === 422 && err.detail?.code === "AMBIGUOUS_CSV_FORMAT") {
        setAmbiguousInfo(err.detail);
        setMapping({
          date: err.detail.suggested_mapping?.date || "",
          description: err.detail.suggested_mapping?.description || "",
          amount: err.detail.suggested_mapping?.amount || "",
          debit: err.detail.suggested_mapping?.debit || "",
          credit: err.detail.suggested_mapping?.credit || "",
          tx_type: err.detail.suggested_mapping?.tx_type || "",
          balance: err.detail.suggested_mapping?.balance || "",
        });
        setError(err.detail.message);
      } else {
        setError(err.message || "Failed to parse CSV statement.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
      <div className="w-full max-w-lg rounded-2xl bg-slate-900 border border-slate-800 p-6 shadow-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <FileSpreadsheet className="h-5 w-5 text-emerald-400" />
            <h2 className="text-lg font-semibold text-white">Upload Bank CSV Statement</h2>
          </div>
          <button onClick={resetAndClose} className="text-slate-400 hover:text-white">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="mb-4 rounded-xl bg-slate-950 border border-slate-800 p-3 text-xs text-slate-400 flex gap-2.5">
          <ShieldCheck className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
          <span>
            Supports <strong className="text-slate-200">SBI, HDFC, ICICI, and Generic</strong> CSV exports (max 5 MB). PII is scrubbed before AI categorization. Never share bank passwords, CVVs, or UPI PINs.
          </span>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <label className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-700 hover:border-emerald-500/60 bg-slate-950/60 p-6 cursor-pointer transition">
            <Upload className="h-7 w-7 text-slate-400 mb-2" />
            <span className="text-sm font-medium text-slate-200">
              {file ? file.name : "Choose a .csv bank statement"}
            </span>
            <span className="text-[11px] text-slate-500 mt-1">
              Duplicates across previous uploads are automatically skipped
            </span>
            <input
              type="file"
              accept=".csv,text/csv"
              className="hidden"
              onChange={(e) => {
                setFile(e.target.files?.[0] || null);
                setAmbiguousInfo(null);
                setError("");
              }}
            />
          </label>

          {ambiguousInfo && (
            <div className="rounded-xl bg-amber-500/10 border border-amber-500/30 p-4 space-y-3">
              <div className="flex items-center gap-2 text-xs font-semibold text-amber-300">
                <SlidersHorizontal className="h-4 w-4" />
                <span>Confirm Column Mapping</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-xs">
                {[
                  ["date", "Date Column *"],
                  ["description", "Description Column *"],
                  ["debit", "Debit / Withdrawal"],
                  ["credit", "Credit / Deposit"],
                  ["amount", "Signed Amount (optional)"],
                  ["tx_type", "Type (DR/CR, optional)"],
                  ["balance", "Balance (optional)"],
                ].map(([field, label]) => (
                  <div key={field}>
                    <label className="block text-[11px] text-slate-400 mb-1">{label}</label>
                    <select
                      value={mapping[field] || ""}
                      onChange={(e) =>
                        setMapping((prev) => ({ ...prev, [field]: e.target.value }))
                      }
                      className="w-full rounded-lg bg-slate-950 border border-slate-700 px-2 py-1.5 text-xs text-slate-200"
                    >
                      <option value="">-- Not mapped --</option>
                      {ambiguousInfo.headers.map((h) => (
                        <option key={h} value={h}>
                          {h}
                        </option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>
            </div>
          )}

          {error && (
            <div className="flex items-start gap-2 rounded-xl bg-rose-500/10 border border-rose-500/30 p-3 text-xs text-rose-300">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={resetAndClose}
              className="px-4 py-2 rounded-xl text-xs font-medium text-slate-300 hover:bg-slate-800"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || !file}
              className="px-4 py-2 rounded-xl text-xs font-semibold bg-emerald-500 hover:bg-emerald-400 text-slate-950 disabled:opacity-50"
            >
              {loading
                ? "Parsing & Categorizing..."
                : ambiguousInfo
                ? "Retry With Column Mapping"
                : "Import & Analyze"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
