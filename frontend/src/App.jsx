import React, { useEffect, useState, useCallback } from "react";

const API = "/api";

function confidenceColor(score) {
  if (score >= 0.9) return "bg-emerald-100 text-emerald-800 border-emerald-300";
  if (score >= 0.7) return "bg-amber-100 text-amber-800 border-amber-300";
  return "bg-rose-100 text-rose-800 border-rose-300";
}

function StatusPill({ status }) {
  const map = {
    approved: "bg-emerald-100 text-emerald-700",
    needs_review: "bg-rose-100 text-rose-700",
    pending: "bg-slate-100 text-slate-600",
    processing: "bg-sky-100 text-sky-700",
    failed: "bg-red-200 text-red-800",
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${map[status] || "bg-slate-100"}`}>
      {status}
    </span>
  );
}

function UploadBox({ onUploaded }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const upload = async (file) => {
    setBusy(true);
    setError(null);
    const form = new FormData();
    form.append("file", file);
    try {
      const res = await fetch(`${API}/documents`, { method: "POST", body: form });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.detail || `Upload failed (${res.status})`);
      } else {
        onUploaded();
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <label className="flex items-center justify-center border-2 border-dashed border-slate-300 rounded-lg p-4 text-sm text-slate-500 cursor-pointer hover:border-sky-400 hover:text-sky-600 transition">
        {busy ? "Uploading…" : "Upload an invoice (PDF/PNG/JPG)"}
        <input
          type="file"
          className="hidden"
          onChange={(e) => e.target.files[0] && upload(e.target.files[0])}
        />
      </label>
      {error && <div className="mt-2 text-xs text-rose-600">{error}</div>}
    </div>
  );
}

function StatTile({ label, value, sub }) {
  return (
    <div className="bg-white border rounded-lg p-4 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</div>
      <div className="text-2xl font-bold text-slate-800 mt-1">{value}</div>
      {sub && <div className="text-xs text-slate-400 mt-1">{sub}</div>}
    </div>
  );
}

const pct = (n) => (n === null || n === undefined ? "—" : `${(n * 100).toFixed(1)}%`);
const ms = (n) => (n === null || n === undefined ? "—" : `${Math.round(n)} ms`);
const usd = (n) => (n === null || n === undefined ? "—" : `$${n.toFixed(4)}`);

function Observability() {
  const [metrics, setMetrics] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const load = () =>
      fetch(`${API}/metrics`)
        .then((r) => r.json())
        .then(setMetrics)
        .catch(() => setError("Could not reach /metrics"));
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, []);

  if (error) return <div className="p-6 text-rose-600 text-sm">{error}</div>;
  if (!metrics) return <div className="p-6 text-slate-400">Loading metrics…</div>;

  const statusEntries = Object.entries(metrics.by_status || {});

  return (
    <div className="p-6 space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-slate-800">Observability</h2>
        <p className="text-xs text-slate-400">
          Computed live from the documents and runs tables. Window: {metrics.window}.
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatTile label="Total documents" value={metrics.total_documents} />
        <StatTile label="Straight-through rate" value={pct(metrics.straight_through_rate)} sub="auto-approved, nothing flagged" />
        <StatTile label="Avg confidence" value={pct(metrics.avg_confidence)} />
        <StatTile label="Corrections logged" value={metrics.corrections_logged} />
        <StatTile label="Avg latency" value={ms(metrics.avg_latency_ms)} />
        <StatTile label="P95 latency" value={ms(metrics.p95_latency_ms)} />
        <StatTile label="Total cost" value={usd(metrics.total_cost_usd)} sub="illustrative, see docs/guardrails.md" />
        <StatTile label="Avg cost / doc" value={usd(metrics.avg_cost_usd_per_doc)} sub="illustrative, see docs/guardrails.md" />
      </div>

      <div>
        <h3 className="text-sm font-semibold text-slate-700 mb-2">Documents by status</h3>
        <div className="flex flex-wrap gap-2">
          {statusEntries.map(([status, count]) => (
            <div key={status} className="flex items-center gap-2 bg-white border rounded-full pl-3 pr-1 py-1">
              <StatusPill status={status} />
              <span className="text-xs text-slate-500 pr-2">{count}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function DocumentDetail({ docId, onSaved }) {
  const [doc, setDoc] = useState(null);
  const [edits, setEdits] = useState({});
  const [saving, setSaving] = useState(null);

  const load = useCallback(() => {
    fetch(`${API}/documents/${docId}`).then((r) => r.json()).then(setDoc);
  }, [docId]);

  useEffect(load, [load]);

  if (!doc) return <div className="p-6 text-slate-400">Loading…</div>;

  const save = async (fieldName) => {
    setSaving(fieldName);
    await fetch(`${API}/documents/${docId}/corrections`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ field_name: fieldName, corrected_value: edits[fieldName], reviewer: "reviewer@docusense" }),
    });
    setSaving(null);
    load();
    onSaved();
  };

  const lastRun = doc.runs && doc.runs.length ? doc.runs[doc.runs.length - 1] : null;

  return (
    <div className="grid grid-cols-2 gap-6 p-6">
      <div>
        <h2 className="text-lg font-semibold mb-2 text-slate-800">{doc.filename}</h2>
        <div className="border rounded-lg overflow-hidden bg-white shadow-sm">
          <img src={`${API}/documents/${docId}/file`} alt={doc.filename} className="w-full object-contain" onError={(e) => (e.target.style.display = "none")} />
        </div>
      </div>
      <div>
        <div className="flex items-center gap-2 mb-2">
          <StatusPill status={doc.status} />
          {doc.flagged_fields?.length > 0 && (
            <span className="text-xs text-slate-500">flagged: {doc.flagged_fields.join(", ")}</span>
          )}
        </div>
        {doc.error && <div className="text-sm text-red-600 mb-3">Error: {doc.error}</div>}
        {lastRun && (
          <div className="text-xs text-slate-400 mb-3">
            {lastRun.model_name} · {lastRun.duration_ms} ms
            {lastRun.pages ? ` · ${lastRun.pages} page${lastRun.pages > 1 ? "s" : ""}` : ""}
            {lastRun.cost_usd != null && <> · ~${lastRun.cost_usd.toFixed(4)} (illustrative)</>}
          </div>
        )}
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="text-left text-slate-500 border-b">
              <th className="py-1 pr-2">Field</th>
              <th className="py-1 pr-2">Value</th>
              <th className="py-1 pr-2">Confidence</th>
              <th className="py-1"></th>
            </tr>
          </thead>
          <tbody>
            {doc.fields.map((f) => (
              <tr key={f.field_name} className="border-b last:border-0">
                <td className="py-2 pr-2 font-mono text-xs text-slate-500">{f.field_name}</td>
                <td className="py-2 pr-2">
                  <input
                    className="w-full border rounded px-2 py-1 text-sm"
                    defaultValue={f.value}
                    onChange={(e) => setEdits((s) => ({ ...s, [f.field_name]: e.target.value }))}
                  />
                </td>
                <td className="py-2 pr-2">
                  <span className={`inline-block px-2 py-0.5 rounded border text-xs font-medium ${confidenceColor(f.confidence)}`}>
                    {(f.confidence * 100).toFixed(0)}%
                  </span>
                </td>
                <td className="py-2">
                  <button
                    className="text-xs px-2 py-1 rounded bg-slate-800 text-white hover:bg-slate-700 disabled:opacity-40"
                    disabled={edits[f.field_name] === undefined || saving === f.field_name}
                    onClick={() => save(f.field_name)}
                  >
                    {saving === f.field_name ? "Saving…" : "Save"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function App() {
  const [docs, setDocs] = useState([]);
  const [filter, setFilter] = useState("");
  const [selected, setSelected] = useState(null);
  const [tab, setTab] = useState("review");

  const refresh = useCallback(() => {
    const qs = filter ? `?status=${filter}` : "";
    fetch(`${API}/documents${qs}`).then((r) => r.json()).then(setDocs);
  }, [filter]);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 4000);
    return () => clearInterval(id);
  }, [refresh]);

  return (
    <div className="min-h-screen">
      <header className="bg-slate-900 text-white px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <div>
            <h1 className="text-xl font-bold">DocuSense</h1>
            <p className="text-xs text-slate-400">Review queue, documents the system was not sure about</p>
          </div>
          <nav className="flex gap-1 bg-slate-800 rounded-full p-1">
            {[
              { key: "review", label: "Review" },
              { key: "observability", label: "Observability" },
            ].map((t) => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`text-xs px-3 py-1.5 rounded-full transition ${tab === t.key ? "bg-sky-500" : "text-slate-300 hover:bg-slate-700"}`}
              >
                {t.label}
              </button>
            ))}
          </nav>
        </div>
        {tab === "review" && (
          <div className="flex gap-2">
            {["", "needs_review", "approved", "pending", "failed"].map((s) => (
              <button
                key={s || "all"}
                onClick={() => setFilter(s)}
                className={`text-xs px-3 py-1.5 rounded-full ${filter === s ? "bg-sky-500" : "bg-slate-700 hover:bg-slate-600"}`}
              >
                {s || "all"}
              </button>
            ))}
          </div>
        )}
      </header>

      {tab === "review" ? (
        <>
          <div className="p-6 max-w-md">
            <UploadBox onUploaded={refresh} />
          </div>

          <div className="grid grid-cols-3 gap-0">
            <div className="col-span-1 border-r bg-white min-h-[60vh]">
              {docs.map((d) => (
                <button
                  key={d.id}
                  onClick={() => setSelected(d.id)}
                  className={`w-full text-left px-4 py-3 border-b hover:bg-slate-50 ${selected === d.id ? "bg-sky-50" : ""}`}
                >
                  <div className="flex justify-between items-center">
                    <span className="text-sm font-medium text-slate-800 truncate">{d.filename}</span>
                    <StatusPill status={d.status} />
                  </div>
                  <div className="text-xs text-slate-400">{new Date(d.uploaded_at).toLocaleString()}</div>
                </button>
              ))}
              {docs.length === 0 && <div className="p-4 text-sm text-slate-400">No documents yet.</div>}
            </div>
            <div className="col-span-2">
              {selected ? <DocumentDetail docId={selected} onSaved={refresh} /> : (
                <div className="p-10 text-slate-400">Select a document to review its extracted fields.</div>
              )}
            </div>
          </div>
        </>
      ) : (
        <Observability />
      )}
    </div>
  );
}
