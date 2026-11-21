import test from 'node:test';
import assert from 'node:assert/strict';
import { guess, review } from '../src/services/statement.js';

const map = {date:0, description:1, debit:2, credit:3, amount:-1};
const r = (number, date, description, debit, credit='') => ({ number, cells:[date, description, debit, credit] });

test('recognizes common bank column names', () => {
  assert.deepEqual(guess(['Txn Date','Narration','Withdrawal','Deposit']), {
    date:0, description:1, debit:2, credit:3, amount:-1
  });
});

test('flags duplicate same-date same-description same-amount debits', () => {
  const result = review([r(2,'2026-11-01','Store A','120.00'),r(3,'2026-11-01','Store A','120.00')], map, false, -1, false);
  assert.equal(result.count,2);
  assert.deepEqual(result.flagged.map(x=>x.row),[2,3]);
  assert.ok(result.flagged.every(x=>x.reasons.some(reason=>reason.includes('Same date'))));
});

test('does not treat credits as suspicious outgoing payments', () => {
  const result = review([r(2,'2026-11-01','Salary','','90000.00')], map, false, -1, false);
  assert.equal(result.count,1);
  assert.equal(result.flagged.length,0);
});

test('flags large debit relative to median when at least five debits exist', () => {
  const values = ['100.00','100.00','100.00','100.00','1000.00'];
  const result = review(values.map((value,i)=>r(i+2,`2026-11-0${i+1}`,`Merchant ${i}`,value)),map,false,-1,false);
  assert.deepEqual(result.flagged.map(x=>x.row),[6]);
});

test('skips malformed monetary values rather than silently treating them as zero', () => {
  const result = review([r(2,'2026-11-01','Malformed','1,2x'),r(3,'2026-11-02','Okay','15.20')],map,false,-1,false);
  assert.deepEqual(result.skipped,[2]);
  assert.equal(result.count,1);
});

test('handles a workbook without any debit payments', () => {
  const result = review([r(2,'2026-11-01','Income','','100.00')],map,false,-1,false);
  assert.equal(result.flagged.length,0);
});
