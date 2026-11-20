const patterns = {
  date: /date/i, description: /description|narration|particulars|remarks|details/i,
  debit: /debit|withdrawal|money out|paid out/i, credit: /credit|deposit|money in|paid in/i,
  amount: /^amount$|transaction amount/i,
};
export function guess(cells) {
  return Object.fromEntries(Object.entries(patterns).map(([key, pattern]) => [key, cells.findIndex(text => pattern.test(text))]));
}
function money(value) {
  const text = String(value ?? '').trim().replace(/^(?:₹|INR|Rs\.?)\s*/i, '').replaceAll(',', '');
  if (!text || text === '-') return 0;
  return /^[+-]?\d+(\.\d{1,2})?$/.test(text) ? Math.round(Number(text)*100) : NaN;
}
function dateText(value, date1904) {
  if (/^\d{4,5}(\.\d+)?$/.test(value)) {
    const epoch = date1904 ? Date.UTC(1904,0,1) : Date.UTC(1899,11,30);
    return new Date(epoch + Math.floor(Number(value))*86400000).toISOString().slice(0,10);
  }
  return value;
}
export function review(rows, map, signed, sign, date1904) {
  const entries = [], skipped = [];
  for (const row of rows) {
    const cells = row.cells;
    const date = dateText(cells[map.date]?.trim() || '', date1904);
    const description = cells[map.description]?.trim();
    const debit = signed ? money(cells[map.amount])*sign : money(cells[map.debit]);
    const credit = signed || map.credit < 0 ? 0 : money(cells[map.credit]);
    if (!date || !description || !Number.isFinite(debit + credit) || (!debit && !credit) ||
        (!signed && (debit < 0 || credit < 0 || (debit && credit)))) {
      skipped.push(row.number); continue;
    }
    entries.push({row:row.number, date, description, debit:Math.max(0,debit), reasons:[]});
  }
  const debits = entries.filter(e => e.debit > 0);
  const amounts = debits.map(e => e.debit).sort((a,b) => a-b);
  const median = (amounts[Math.floor((amounts.length-1)/2)] + amounts[Math.floor(amounts.length/2)])/2;
  const groups = new Map();
  for (const e of debits) {
    const key = JSON.stringify([e.date,e.description.toLowerCase().replace(/\s+/g,' '),e.debit]);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(e);
    if (amounts.length >= 5 && e.debit >= 5*median) e.reasons.push('At least five times the median debit in this sheet.');
  }
  for (const group of groups.values()) if (group.length > 1) {
    for (const e of group) e.reasons.push('Same date, description and amount appear more than once.');
  }
  return {count:entries.length, skipped, flagged:debits.filter(e => e.reasons.length)};
}
