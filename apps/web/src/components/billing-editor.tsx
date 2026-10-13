'use client';
import { useState } from 'react';
import { api } from '@/lib/api';
import type { BillingLineInput, BillingSplit, EncounterDetail, SourceSpan } from '@/lib/types';

const input = 'mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500';
const revenues = { ER_FACILITY: '0450 · Emergency room', ER_SCREENING: '0451 · EMTALA screening', LABORATORY: '0300 · Laboratory', LAB_HEMATOLOGY: '0305 · Hematology', RADIOLOGY_DIAG: '0320 · Diagnostic radiology', CT_SCAN: '0350 · CT scan', PHARMACY: '0250 · Pharmacy', IV_THERAPY: '0260 · IV therapy', SUPPLIES: '0270 · Supplies', EKG: '0730 · EKG' };
type Draft = Omit<BillingLineInput, 'units' | 'diagnosis_pointers'> & { key: string; unitsText: string; pointersText: string };

// DOM textareas normalize CRLF and count UTF-16; the API uses original Unicode offsets.
function originalSpan(text: string, start: number, end: number, page_number: number): SourceSpan {
  const points = Array.from(text);
  const boundaries = new Map<number, number>();
  let dom = 0;
  for (let i = 0; i < points.length; i++) {
    boundaries.set(dom, i);
    if (points[i] === '\r' && points[i + 1] === '\n') i++;
    dom += points[i].length;
  }
  boundaries.set(dom, points.length);
  const from = boundaries.get(start);
  const to = boundaries.get(end);
  if (from === undefined || to === undefined) throw new Error('Select complete source characters.');
  return { page_number, start_offset: from, end_offset: to, quoted_text: points.slice(from, to).join('') };
}

export function BillingEditor({ encounter, onSaved, initialOpen = true }: { encounter: EncounterDetail; onSaved: (split: BillingSplit) => Promise<void>; initialOpen?: boolean }) {
  const [diagnoses, setDiagnoses] = useState<string[]>([]);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [notes, setNotes] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [pageIndex, setPageIndex] = useState(0);
  const [span, setSpan] = useState<SourceSpan | null>(null);
  const approved = encounter.candidate_codes.filter(c => c.status === 'approved' && !c.human_review_required);
  const dx = approved.filter(c => c.code_system === 'ICD-10-CM');
  const services = approved.filter(c => ['CPT', 'HCPCS'].includes(c.code_system));
  const sourceId = approved.flatMap(c => c.supporting_evidence)[0]?.document_id;
  const pages = encounter.documents.find(d => d.id === sourceId)?.pages || [];
  const page = pages[pageIndex];
  const evidence = [...new Map(approved.flatMap(c => c.supporting_evidence).filter(e => e.id).map(e => [e.id!, e])).values()];
  const update = (key: string, patch: Partial<Draft>) => setDrafts(prev => prev.map(d => d.key === key ? { ...d, ...patch } : d));
  async function save(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      if (!drafts.length || !diagnoses.length) throw new Error('Select the diagnosis sequence and add at least one billing line.');
      const lines = drafts.map(({ key, unitsText, pointersText, ...line }) => { void key; return { ...line, units: Number(unitsText), diagnosis_pointers: pointersText.split(',').map(p => Number(p.trim())) }; });
      const split = await api.acceptBillingSplit(encounter.id, { version: encounter.version, snapshot_id: encounter.snapshot_id!, diagnosis_candidate_ids: diagnoses, lines, notes });
      await onSaved(split);
    } catch (err) { setError(err instanceof Error ? err.message : 'Billing review failed.'); }
    finally { setBusy(false); }
  }
  return <details className="rounded-xl border border-blue-200 bg-white shadow-sm" open={initialOpen}><summary className="cursor-pointer p-5 font-semibold">Review ED billing lines</summary>
    <form onSubmit={save} className="space-y-5 border-t p-5">
      <p className="text-sm text-slate-600">Select claim lines explicitly. Facility resources and modifiers need evidence. Full payer and NCCI verification is unavailable.</p>
      {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      <fieldset disabled={busy} className="space-y-5 disabled:opacity-60">
        <div><h3 className="text-sm font-semibold">Diagnosis sequence</h3><p className="text-xs text-slate-500">Select in claim order. A is primary; use arrows to change order.</p><div className="mt-2 flex flex-wrap gap-2">{dx.map(c => <label key={c.id} className="rounded-lg border px-3 py-2 text-sm"><input type="checkbox" checked={diagnoses.includes(c.id)} onChange={e => setDiagnoses(prev => e.target.checked ? [...prev, c.id] : prev.filter(id => id !== c.id))} /> {c.code}</label>)}</div><ol className="mt-2 space-y-1">{diagnoses.map((id, i) => <li key={id} className="flex items-center gap-3 text-sm"><strong>{String.fromCharCode(65 + i)}. {dx.find(c => c.id === id)?.code}</strong><button type="button" disabled={i === 0} aria-label={`Move diagnosis ${i + 1} up`} onClick={() => setDiagnoses(prev => { const next = [...prev]; [next[i - 1], next[i]] = [next[i], next[i - 1]]; return next; })} className="rounded border px-2 disabled:opacity-30">↑</button></li>)}</ol></div>
        <div className="rounded-lg bg-slate-50 p-4"><label className="text-sm font-semibold">Source page<select aria-label="Source page" className={input} value={pageIndex} onChange={e => { setPageIndex(Number(e.target.value)); setSpan(null); }}>{pages.map((p, i) => <option key={p.page_number} value={i}>Page {p.page_number}</option>)}</select></label><p className="my-2 text-xs text-slate-600">Select exact facility resource text below, then attach it to a facility line.</p><textarea aria-label="Facility source text" readOnly value={page?.ocr_text || ''} className={`${input} h-48 font-mono text-xs`} onSelect={e => { const el = e.currentTarget; if (page && el.selectionEnd > el.selectionStart) { try { setSpan(originalSpan(page.ocr_text, el.selectionStart, el.selectionEnd, page.page_number)); } catch (err) { setSpan(null); setError((err as Error).message); } } }} />{span && <p className="mt-2 text-xs text-blue-700">Selected: {span.quoted_text}</p>}</div>
        {drafts.map((d, index) => { const candidate = services.find(c => c.id === d.candidate_id); return <div key={d.key} className="space-y-3 rounded-xl border p-4"><div className="flex justify-between"><h3 className="font-semibold">Line {index + 1}</h3><button type="button" className="text-xs text-red-700" onClick={() => setDrafts(prev => prev.filter(row => row.key !== d.key))}>Remove line {index + 1}</button></div><div className="grid gap-3 sm:grid-cols-3">
          <label className="text-xs font-medium">Claim<select className={input} value={d.claim_type} onChange={e => update(d.key, { claim_type: e.target.value as Draft['claim_type'], revenue_category: undefined, facility_basis: undefined, facility_policy_reference: undefined })}><option value="professional">CMS-1500 · Professional</option><option value="facility">UB-04 · Facility</option></select></label>
          <label className="text-xs font-medium">Approved service code<select required className={input} value={d.candidate_id} onChange={e => update(d.key, { candidate_id: e.target.value, supporting_evidence_ids: [] })}><option value="">Select code</option>{services.map(c => <option key={c.id} value={c.id}>{c.code_system} {c.code}</option>)}</select></label>
          <label className="text-xs font-medium">Service category<select className={input} value={d.service_type} onChange={e => update(d.key, { service_type: e.target.value as Draft['service_type'] })}>{['EM', 'PROCEDURE', 'LAB', 'RADIOLOGY', 'MEDICATION', 'INFUSION', 'SUPPLY', 'EKG'].map(t => <option key={t}>{t}</option>)}</select></label>
          <label className="text-xs font-medium">Units<input required type="number" min="1" max="10000" step="1" className={input} value={d.unitsText} onChange={e => update(d.key, { unitsText: e.target.value })} /></label>
          <label className="text-xs font-medium">Diagnosis positions (e.g. 1,2)<input required className={input} value={d.pointersText} onChange={e => update(d.key, { pointersText: e.target.value })} /></label>
          <label className="text-xs font-medium">Supporting evidence<select required className={input} value={d.supporting_evidence_ids[0] || ''} onChange={e => update(d.key, { supporting_evidence_ids: [e.target.value] })}><option value="">Select source evidence</option>{candidate?.supporting_evidence.map(ev => <option key={ev.id} value={ev.id}>Page {ev.page_number}: {ev.quoted_text}</option>)}</select></label>
          <label className="text-xs font-medium">Modifiers<select multiple className={input} value={d.modifiers} onChange={e => update(d.key, { modifiers: Array.from(e.target.selectedOptions, o => o.value) as Draft['modifiers'], modifier_basis_evidence_ids: [] })}>{['25', '26', 'TC', 'RT', 'LT'].map(m => <option key={m}>{m}</option>)}</select><span className="text-slate-500">Optional, at most two.</span></label>
          {d.modifiers.length > 0 && <label className="text-xs font-medium">Modifier evidence<select required className={input} value={d.modifier_basis_evidence_ids[0] || ''} onChange={e => update(d.key, { modifier_basis_evidence_ids: [e.target.value] })}><option value="">Select documented basis</option>{evidence.map(ev => <option key={ev.id} value={ev.id}>Page {ev.page_number}: {ev.quoted_text}</option>)}</select></label>}
          {d.modifiers.some(m => ['26', 'TC'].includes(m)) && <label className="text-xs font-medium">PC/TC policy reference<input required className={input} value={d.component_policy_reference || ''} onChange={e => update(d.key, { component_policy_reference: e.target.value })} /></label>}
          {d.claim_type === 'facility' && <><label className="text-xs font-medium">Revenue category<select required className={input} value={d.revenue_category || ''} onChange={e => update(d.key, { revenue_category: e.target.value })}><option value="">Select revenue category</option>{Object.entries(revenues).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label><label className="text-xs font-medium">Hospital policy reference<input required className={input} value={d.facility_policy_reference || ''} onChange={e => update(d.key, { facility_policy_reference: e.target.value })} /></label><div className="text-xs"><button type="button" disabled={!span} className="mt-4 rounded-lg border border-blue-300 px-3 py-2 text-blue-700 disabled:opacity-40" onClick={() => update(d.key, { facility_basis: span! })}>Attach selected resource text</button>{d.facility_basis && <p className="mt-2 text-slate-600">Page {d.facility_basis.page_number}: {d.facility_basis.quoted_text}</p>}</div></>}
        </div></div>; })}
        <button type="button" className="rounded-lg border px-3 py-2 text-sm" onClick={() => setDrafts(prev => [...prev, { key: crypto.randomUUID(), claim_type: 'professional', candidate_id: '', service_type: 'EM', unitsText: '', pointersText: '', modifiers: [], supporting_evidence_ids: [], modifier_basis_evidence_ids: [] }])}>Add billing line</button>
        <label className="block text-sm font-medium">Billing review notes<textarea required maxLength={4000} className={input} value={notes} onChange={e => setNotes(e.target.value)} /></label><button type="submit" className="rounded-lg bg-blue-700 px-4 py-2.5 font-semibold text-white">{busy ? 'Validating billing review…' : 'Accept billing selections'}</button>
      </fieldset>
    </form>
  </details>;
}
