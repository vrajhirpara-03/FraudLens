import Statement from './Statement';
import React, { useEffect, useState } from 'react';
import { getHealth, getModel, predictCSV } from './services/api';

function Benchmark() {
  const [model, setModel] = useState(null);
  const [error, setError] = useState('');
  const [results, setResults] = useState(null);
  const [busy, setBusy] = useState(false);
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState('Checking connection');
  useEffect(() => {
    const controller = new AbortController();
    getHealth(controller.signal)
      .then(data => setStatus(data.status === 'ok' ? 'API connected' : 'API unavailable'))
      .catch(error => { if (error.name !== 'AbortError') setStatus('API offline'); });
    getModel(controller.signal).then(setModel).catch(error => { if (error.name !== 'AbortError') setError(error.message); });
    return () => controller.abort();
  }, []);

  async function upload(event) {
    event.preventDefault();
    setError(''); setResults(null);
    if (!file) { setError('Choose a CSV first.'); return; }
    if (file.size > 1000000) { setError('Choose a CSV smaller than 1 MB, with at most 1,000 rows.'); return; }
    setBusy(true);
    try { setResults(await predictCSV(file)); } catch (error) { setError(error.message); }
    finally { setBusy(false); }
  }
  const metrics = model?.report.test;
  const percent = value => value == null ? '—' : `${(value * 100).toFixed(2)}%`;
  return (
    <div className="shell">
      <aside><a className="brand" href="/">◈ FraudLens</a><p className="label">WORKSPACE</p><span className="active">Overview</span><div className="aside-note">Built for evidence.<br/>Designed for clarity.</div></aside>
      <main>
        <header><span>Workspace / Overview</span><span className="connection"><i />{status}</span></header>
        <section className="intro"><p className="label">TRANSACTION INTELLIGENCE</p><h1>See the risk.<br/><span>Understand the signal.</span></h1><p>A workspace for exploring credit card fraud, evaluating models, and reviewing transaction risk.</p></section>
        <div className="cards">
          <article><p className="label">MODEL STATUS</p><h2>{model ? 'Baseline ready' : 'Unavailable'}</h2><p>Logistic regression · chronological test evaluation</p></article>
          <article><p className="label">PRECISION / RECALL</p><h2>{percent(metrics?.precision)} / {percent(metrics?.recall)}</h2><p>How reliable alerts are / how much fraud is caught</p></article>
          <article><p className="label">AVERAGE PRECISION</p><h2>{metrics?.average_precision.toFixed(4) ?? '—'}</h2><p>Ranking performance across precision–recall thresholds</p></article>
        </div>
        {metrics && <section className="evaluation"><h2>Know what the model misses.</h2><p>On {model.report.splits.test.rows.toLocaleString()} held-out transactions: <strong>{metrics.confusion_matrix.tp} fraud detected, {metrics.confusion_matrix.fn} missed, {metrics.confusion_matrix.fp} false alarms.</strong></p><p>Historical, anonymized benchmark. These results do not establish performance on current payment traffic.</p></section>}
        <section className="roadmap"><div><p className="label">TRANSACTION CHECKER</p><h2>Review a batch.</h2><p>Upload a UTF-8 CSV with Time, V1–V28, and Amount. Class is optional and ignored for predictions. Maximum 1 MB / 1,000 transactions.</p><p>The anonymized features are required. Card numbers and payment details cannot replace them.</p></div><form onSubmit={upload}><label htmlFor="csv">Transaction CSV</label><input id="csv" type="file" accept=".csv,text/csv" disabled={busy} onChange={event => { setFile(event.target.files[0] || null); setResults(null); setError(''); }} /><button disabled={busy || !model || !file}>{busy ? 'Checking…' : 'Check transactions'}</button><p>Output is an uncalibrated model score, not a verified fraud probability. A transaction below threshold can still be fraudulent.</p></form></section>
        {error && <p className="error" role="alert">{error}</p>}
        {results && <section aria-live="polite"><h2>Review results</h2><p>{results.results.filter(row => row.flagged_for_review).length} of {results.results.length} flagged for review. Threshold: {results.threshold.toPrecision(10)}.</p><div className="table-wrap"><table><thead><tr><th>CSV transaction</th><th>Model score</th><th>Decision</th></tr></thead><tbody>{results.results.map(row => <tr key={row.row}><td>{row.row}</td><td>{row.model_score.toPrecision(10)}</td><td>{row.flagged_for_review ? 'Flagged for review' : 'Not flagged'}</td></tr>)}</tbody></table></div></section>}
        <footer>FraudLens · Development milestone 04<span>Research prototype</span></footer>
      </main>
    </div>
  );
}

export default function App() {
  const [page, setPage] = useState('statement');
  return <><nav className="mode-nav" aria-label="Workspace">
    <button aria-pressed={page==='statement'} onClick={()=>setPage('statement')}>Bank statement review</button>
    <button aria-pressed={page==='benchmark'} onClick={()=>setPage('benchmark')}>ML benchmark</button>
  </nav>{page==='statement' ? <main><Statement /></main> : <Benchmark />}</>;
}
