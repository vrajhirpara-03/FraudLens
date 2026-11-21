import React, { useState } from 'react';
import { guess, review } from './services/statement';
import { uploadWorkbook } from './services/api';

export default function Statement() {
  const [book, setBook] = useState(null), [sheet, setSheet] = useState(0);
  const [header, setHeader] = useState(0), [map, setMap] = useState({});
  const [signed, setSigned] = useState(false), [sign, setSign] = useState(-1);
  const [result, setResult] = useState(null), [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const rows = book?.sheets[sheet].rows || [];
  const headers = rows[header]?.cells || [];

  function selectHeader(data, index) {
    const mapping = guess(data[index].cells);
    setHeader(index); setMap(mapping); setSigned(mapping.debit < 0 && mapping.amount >= 0);
    setResult(null); setError('');
  }
  function selectSheet(workbook, index) {
    const data = workbook.sheets[index].rows;
    const first = data.findIndex(row => {
      const m = guess(row.cells);
      return m.date >= 0 && (m.debit >= 0 || m.amount >= 0);
    });
    setSheet(index); selectHeader(data, Math.max(0, first));
  }
  async function load(file) {
    setBusy(true); setError(''); setBook(null); setResult(null);
    try {
      if (file.size > 5000000) throw Error('Choose a workbook smaller than 5 MB.');
      const data = await uploadWorkbook(file);
      setBook(data); selectSheet(data,0);
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  function run() {
    const required = ['date','description',...(signed ? ['amount'] : ['debit'])];
    const used = required.map(key => map[key]);
    if (!signed && map.credit >= 0) used.push(map.credit);
    if (used.some(i => i < 0) || new Set(used).size !== used.length) {
      setError('Choose a different column for each required field.'); return;
    }
    setError(''); setResult(review(rows.slice(header+1), map, signed, sign, book.date1904));
  }
  const fields = signed ? ['date','description','amount'] : ['date','description','debit','credit'];
  return <section className="statement"><h1>Review a bank statement</h1>
    <p>Choose an Excel statement to check for possible double charges and unusually large payments. FraudLens reads the file in memory on the configured API server. For privacy, use only fictional or authorized test statements in a public demo.</p>
    <label>Bank statement (.xlsx, up to 5 MB) <input type="file" accept=".xlsx" disabled={busy} onChange={e => {const file=e.target.files[0]; e.target.value=''; if(file) load(file);}} /></label>
    <p><a href="/sample-statement.xlsx" download>Download a fictional sample statement</a></p>
    {busy && <p role="status">Reading workbook…</p>}
    {book && <><h2>Check the columns</h2>
    <label>Worksheet <select value={sheet} onChange={e=>selectSheet(book,+e.target.value)}>{book.sheets.map((s,i)=><option key={i} value={i}>{s.name}</option>)}</select></label>
    <label>Row containing column names <select value={header} onChange={e=>selectHeader(rows,+e.target.value)}>{rows.map((r,i)=><option key={i} value={i}>Row {r.number} · {r.cells.join(' / ').slice(0,65)}</option>)}</select></label>
    <label>Payment layout <select value={signed?'signed':'split'} onChange={e=>{setSigned(e.target.value==='signed');setResult(null);}}><option value="split">Separate debit and credit columns</option><option value="signed">One signed amount column</option></select></label>
    {signed && <label>Outgoing payments have <select value={sign} onChange={e=>{setSign(+e.target.value);setResult(null);}}><option value={-1}>Negative amounts</option><option value={1}>Positive amounts</option></select></label>}
    <div className="mapping">{fields.map(key=><label key={key}>{key}{key==='credit'?' (optional)':''} <select value={map[key]} onChange={e=>{setMap({...map,[key]:+e.target.value});setResult(null);}}><option value={-1}>Choose column</option>{headers.map((h,i)=><option key={i} value={i}>{h || 'Column '+(i+1)}</option>)}</select></label>)}</div>
    <h3>Preview the first five rows</h3><div className="table-wrap"><table><thead><tr>{fields.map(k=><th key={k}>{k}</th>)}</tr></thead><tbody>{rows.slice(header+1,header+6).map(r=><tr key={r.number}>{fields.map(k=><td key={k}>{r.cells[map[k]] || '—'}</td>)}</tr>)}</tbody></table></div>
    <button onClick={run}>Confirm columns and review</button></>}
    {error && <p role="alert">{error}</p>}
    {result && <section aria-live="polite"><h2>{result.flagged.length} payments worth checking</h2>
    <p>{result.count} transactions reviewed. Check flagged payments against your receipts.</p>
    {!!result.skipped.length && <p>{result.skipped.length} rows could not be reviewed. Check the mapping or correct the workbook. Sheet rows {result.skipped.slice(0,25).join(', ')}{result.skipped.length>25?'…':''}.</p>}
    {result.flagged.map(e=><article key={e.row}><strong>{e.description} · {(e.debit/100).toFixed(2)}</strong><p>{e.date} · Sheet row {e.row}</p><p>{e.reasons.join(' ')}</p></article>)}</section>}
  </section>;
}
