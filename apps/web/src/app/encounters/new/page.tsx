'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { UploadCloud, Download, Loader2, ArrowLeft, Layers } from 'lucide-react';
import { api } from '@/lib/api';
import type { BillingSplit, EncounterDetail } from '@/lib/types';
import { BillingEditor } from '@/components/billing-editor';

const input = 'mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500';
const pendingStates = ['created', 'ingesting', 'processing', 'ocr_ready', 'facts_ready', 'candidates_ready'];

export default function NewEncounterPage() {
  const [file, setFile] = useState<File | null>(null);
  const [domain, setDomain] = useState('');
  const [pos, setPos] = useState('');
  const [patient, setPatient] = useState('');
  const [date, setDate] = useState('');
  const [busy, setBusy] = useState(false);
  const [phase, setPhase] = useState('');
  const [error, setError] = useState('');
  const [suggestion, setSuggestion] = useState('');
  const [encounter, setEncounter] = useState<EncounterDetail | null>(null);
  const [caseId, setCaseId] = useState<string | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [notes, setNotes] = useState('');
  const [split, setSplit] = useState<BillingSplit | null>(null);
  const [tab, setTab] = useState<'professional' | 'facility'>('professional');
  const [canReview, setCanReview] = useState(false);
  const [imageOcr, setImageOcr] = useState(false);
  const [referenceStatus, setReferenceStatus] = useState('Checking reference package…');
  useEffect(() => {
    let cancelled = false;
    api.getCapabilities().then(c => { if (!cancelled) { setImageOcr(c.image_ocr_available); setReferenceStatus(c.cms_references.status === 'available' ? `CMS ${c.cms_references.release} reference checks loaded` : 'CMS reference checks unavailable; development catalogs only'); } }).catch(() => { if (!cancelled) setReferenceStatus('Reference status unavailable'); });
    api.getMe().then(user => { if (!cancelled) setCanReview(['Owner', 'Reviewer'].includes(user.role)); }).catch(err => { if (!cancelled) setError(err.message); });
    const id = new URLSearchParams(window.location.search).get('case');
    if (id) api.getEncounter(id).then(result => { if (!cancelled) { setCaseId(id); setEncounter(result); } }).catch(err => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, []);
  useEffect(() => {
    if (!encounter || !pendingStates.includes(encounter.status)) return;
    let cancelled = false;
    const timer = setInterval(async () => {
      try { const next = await api.getEncounter(encounter.id); if (!cancelled) { setEncounter(next); setPhase(`Server status: ${next.status.replaceAll('_', ' ')}`); } }
      catch (err) { if (!cancelled) setError(err instanceof Error ? err.message : 'Status refresh failed.'); }
    }, 2500);
    return () => { cancelled = true; clearInterval(timer); };
  }, [encounter]);
  const approved = !!encounter && ['approved', 'exported'].includes(encounter.status);
  async function reanalyze() {
    if (!encounter) return;
    setBusy(true); setError('');
    try {
      await api.reanalyzeEncounter(encounter.id, encounter.version);
      setSelected([]); setSplit(null);
      setEncounter(await api.getEncounter(encounter.id));
      setPhase('Source reanalysis queued. Review the new results before export.');
    } catch (err) { setError(err instanceof Error ? err.message : 'Reanalysis failed.'); }
    finally { setBusy(false); }
  }
  useEffect(() => {
    if (!encounter || !approved || encounter.coding_domain !== 'emergency_department') return;
    let cancelled = false;
    api.getBillingSplit(encounter.id).then(result => { if (!cancelled) setSplit(result.split); }).catch(err => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [encounter, approved]);

  function chooseFile(next?: File) {
    setSuggestion(''); setError('');
    if (!next) { setFile(null); return; }
    if (!(imageOcr ? /\.(pdf|txt|png|jpe?g|tiff?)$/i : /\.(pdf|txt)$/i).test(next.name)) { setFile(null); setError(imageOcr ? 'Use PDF, PNG, JPEG, TIFF or UTF-8 text.' : 'Image OCR is unavailable. Use a searchable PDF or UTF-8 text.'); return; }
    if (!next.size || next.size > 25 * 1024 * 1024) { setFile(null); setError('Choose a nonempty file up to 25 MB.'); return; }
    setFile(next);
  }
  async function detect() {
    if (!file) return; setBusy(true); setPhase('Inspecting source text for setting clues…'); setError('');
    try { const result = await api.detectSetting(file); setSuggestion(result.coding_domain ? `${result.coding_domain === 'emergency_department' ? 'Emergency Department · POS 23' : 'Professional / Office · POS 11'} suggested. Confirm using the setting dropdown.` : result.message); }
    catch (err) { setError(err instanceof Error ? err.message : 'Detection failed.'); }
    finally { setBusy(false); setPhase(''); }
  }
  async function analyze(event: React.FormEvent) {
    event.preventDefault(); if (!file) return; setBusy(true); setError(''); setSplit(null); setSelected([]);
    try {
      let id = caseId;
      if (!id) { setPhase('Creating encounter…'); const created = await api.createEncounter({ patient_reference: patient.trim(), service_date: date, coding_domain: domain, place_of_service: pos }); id = created.id; setCaseId(id); window.history.replaceState(null, '', `?case=${encodeURIComponent(id)}`); }
      setPhase('Uploading document and awaiting server analysis…'); await api.uploadDocument(id, file);
      const review = await api.getEncounter(id); setEncounter(review); setPhase(`Server status: ${review.status.replaceAll('_', ' ')}`);
    } catch (err) { setError(err instanceof Error ? err.message : 'Analysis failed.'); }
    finally { setBusy(false); }
  }
  async function approve() {
    if (!encounter) return; setBusy(true); setError('');
    try { await api.submitReview(encounter.id, 'accept', notes, selected, encounter.version, Object.fromEntries(encounter.candidate_codes.filter(c => selected.includes(c.id)).map(c => [c.id, c.proposed_modifiers || []]))); setEncounter(await api.getEncounter(encounter.id)); }
    catch (err) { setError(err instanceof Error ? err.message : 'Approval failed.'); }
    finally { setBusy(false); }
  }
  async function download(format: 'collaboratemd' | 'json') {
    if (!encounter) return; setBusy(true); setError('');
    try { await api.downloadExport(encounter.id, format); }
    catch (err) { setError(err instanceof Error ? err.message : 'Download failed.'); }
    finally { setBusy(false); }
  }
  const rows = split ? (tab === 'professional' ? split.cms1500_lines : split.ub04_lines) : approved && tab === 'professional' ? encounter!.candidate_codes.filter(c => c.status === 'approved' && ['CPT', 'HCPCS'].includes(c.code_system)).map(c => ({ candidate_id: c.id, dos: encounter!.service_date, cpt: c.code, primary_dx: '', secondary_dx: '', pointer: '', units: null, mod: (c.proposed_modifiers || []).join(', '), rev_code: undefined, justification: c.supporting_evidence.map(ev => `Page ${ev.page_number}: ${ev.quoted_text}`).join('\n') })) : [];
  return <div className="mx-auto max-w-7xl space-y-6 px-4 py-8 sm:px-8">
    <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-6"><div><Link href="/encounters" className="mb-3 inline-flex items-center gap-1 text-sm text-slate-500"><ArrowLeft className="h-4 w-4" />Encounters</Link><h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Medical Coding &amp; Claim Entry Workspace</h1><p className="mt-2 text-sm text-slate-500">Upload, inspect evidence, approve codes and review claim lines in one workspace.</p></div><span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs font-medium text-amber-800">Development catalogs · Human approval required</span></header>
    {error && <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>}
    {!encounter && <form onSubmit={analyze} className="grid gap-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm lg:grid-cols-3">
      <div className="lg:col-span-2"><h2 className="mb-3 text-sm font-semibold">1. Upload encounter record</h2><label onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); if (!busy) chooseFile(e.dataTransfer.files[0]); }} className="flex min-h-44 cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-slate-300 bg-slate-50 p-6 text-center hover:border-blue-400"><UploadCloud className="h-10 w-10 text-slate-400" /><span className="text-sm font-medium">{file ? file.name : 'Click to upload or drag & drop'}</span><span className="text-xs text-slate-500">{imageOcr ? 'PDF, PNG, JPEG, TIFF or UTF-8 text' : 'Searchable PDF or UTF-8 text'} · Up to 25 MB</span><input aria-label="Upload medical record" disabled={busy} type="file" accept={imageOcr ? '.pdf,.txt,.png,.jpg,.jpeg,.tif,.tiff' : '.pdf,.txt'} className="sr-only" onClick={e => { e.currentTarget.value = ''; }} onChange={e => chooseFile(e.target.files?.[0])} /></label>{file && <button type="button" disabled={busy} onClick={() => chooseFile()} className="mt-2 text-xs text-slate-500">Remove {file.name} ({(file.size / 1024).toFixed(1)} KB)</button>}<p className="mt-3 text-xs text-slate-500">{imageOcr ? 'Local OCR is available for scanned PDFs and images. Verify extracted text against the original.' : 'Scanned PDFs and images need local Tesseract installed.'} {referenceStatus}.</p></div>
      <fieldset disabled={busy} className="space-y-3"><label className="block text-sm font-semibold">2. Confirm setting<select required disabled={!!caseId || busy} className={input} value={domain} onChange={e => { setDomain(e.target.value); setPos(({ emergency_department: '23', professional_office: '11', dme: '12' } as Record<string, string>)[e.target.value] || ''); }}><option value="">Select setting</option><option value="emergency_department">Emergency Department · POS 23</option><option value="professional_office">Professional / Office · POS 11</option><option value="behavioral_health">Behavioral Health</option><option value="dme">DME · Home use · POS 12</option></select></label><button type="button" disabled={!file || !!caseId} onClick={detect} className="text-xs font-semibold text-blue-700 disabled:opacity-40">Suggest setting from document</button>{suggestion && <p className="rounded-lg bg-amber-50 p-2 text-xs text-amber-800">{suggestion}</p>}{domain === 'behavioral_health' && <label className="block text-xs font-medium">Confirmed patient setting<select required className={input} value={pos} onChange={e => setPos(e.target.value)}><option value="">Select documented setting</option><option value="11">In person · POS 11</option><option value="10">Telehealth at home · POS 10</option><option value="02">Telehealth elsewhere · POS 02</option></select></label>}<label className="block text-xs font-medium">Patient pseudonymous reference<input required disabled={!!caseId} maxLength={255} className={input} value={patient} onChange={e => setPatient(e.target.value)} placeholder="SYNTH-001" /></label><label className="block text-xs font-medium">Service date<input required disabled={!!caseId} type="date" className={input} value={date} onChange={e => setDate(e.target.value)} /></label><button disabled={!file || busy} type="submit" className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-700 px-4 py-3 text-sm font-semibold text-white disabled:opacity-40">{busy && <Loader2 className="h-4 w-4 animate-spin" />}{busy ? 'Processing…' : caseId ? 'Retry document analysis' : 'Start Analysis & Coding'}</button></fieldset>
    </form>}
    {phase && (busy || !encounter) && <p role="status" className="text-sm text-slate-600">{phase}</p>}
    {encounter && <>
      {encounter.specialty_status && !pendingStates.includes(encounter.status) && <section aria-label="Specialty availability" className="rounded-xl border border-amber-200 bg-amber-50 p-4"><h2 className="font-semibold">{encounter.specialty_status.status}</h2>{encounter.specialty_status.errors.map(message => <p key={message} className="mt-2 text-sm text-amber-900">{message}</p>)}{encounter.specialty_status.warnings?.map(message => <p key={message} className="mt-2 text-xs text-amber-900">{message}</p>)}</section>}
      <div className="flex flex-wrap justify-between gap-3 rounded-xl border border-slate-200 bg-white p-5"><div><h2 className="font-semibold">{encounter.patient_reference}</h2><p className="text-sm text-slate-500">DOS {encounter.service_date} · POS {encounter.place_of_service} · {encounter.status.replaceAll('_', ' ')}</p></div><div className="flex items-center gap-4"><Link href={`/encounters/${encounter.id}/review`} className="text-sm font-semibold text-blue-700">Detailed evidence review</Link><a href="/encounters/new" className="text-sm text-slate-600">New case</a>{canReview && <button type="button" disabled={busy || pendingStates.includes(encounter.status)} onClick={reanalyze} className="text-sm text-blue-700 disabled:opacity-40">Reanalyze source</button>}</div></div>
      {!approved && <section className="rounded-xl border border-slate-200 bg-white p-5"><h2 className="mb-4 font-semibold">3. Review extracted candidates</h2>{!encounter.candidate_codes.length && <p className="text-sm text-slate-500">{pendingStates.includes(encounter.status) ? 'Waiting for server analysis. Results refresh automatically.' : 'No candidates available. Open detailed review to inspect processing findings or upload a corrected source.'}</p>}<div className="grid gap-3 sm:grid-cols-2">{encounter.candidate_codes.map(c => <label key={c.id} className="rounded-lg border border-slate-200 p-4"><div className="flex items-center gap-2"><input type="checkbox" disabled={busy || !canReview} checked={selected.includes(c.id)} onChange={e => setSelected(prev => e.target.checked ? [...prev, c.id] : prev.filter(id => id !== c.id))} /><strong className="font-mono text-blue-900">{c.code}{c.proposed_modifiers?.length ? `-${c.proposed_modifiers.join('-')}` : ''}</strong><span className="text-xs text-slate-500">{c.code_system}</span></div><p className="my-2 text-xs text-slate-600">{c.rationale}</p>{!!c.proposed_modifiers?.length && <p className="mb-2 text-xs font-semibold text-blue-800">Selecting this candidate accepts the displayed code and proposed modifiers.</p>}{c.supporting_evidence.map(ev => <blockquote key={ev.id} className="my-1 border-l-2 border-blue-200 pl-3 text-xs text-slate-600">Page {ev.page_number}: {ev.quoted_text}</blockquote>)}{c.rule_results.filter(r => r.status === 'FAIL' || r.status === 'WARNING').map(r => <p key={r.rule_id} className="mt-2 text-xs text-amber-800">{r.status}: {r.message}</p>)}</label>)}</div>{canReview && encounter.candidate_codes.length > 0 && <><label className="mt-4 block text-sm font-medium">Coding review notes<textarea className={input} value={notes} onChange={e => setNotes(e.target.value)} /></label><button disabled={busy || !selected.length || pendingStates.includes(encounter.status)} onClick={approve} className="mt-3 rounded-lg bg-blue-700 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-40">Approve selected codes</button></>}</section>}
      {approved && encounter.coding_domain === 'emergency_department' && canReview && <BillingEditor key={`${encounter.id}:${encounter.version}`} initialOpen={!split} encounter={encounter} onSaved={async result => { setSplit(result); setEncounter(await api.getEncounter(encounter.id)); }} />}
      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm"><div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-slate-50 p-4"><div role="tablist" aria-label="Claim results" className="flex rounded-lg bg-slate-200 p-1"><button role="tab" aria-selected={tab === 'professional'} onClick={() => setTab('professional')} className={`rounded-md px-3 py-2 text-xs font-semibold ${tab === 'professional' ? 'bg-white text-blue-700 shadow-sm' : 'text-slate-600'}`}>CMS-1500 · Professional</button>{encounter.coding_domain === 'emergency_department' && <button role="tab" aria-selected={tab === 'facility'} onClick={() => setTab('facility')} className={`flex items-center gap-1 rounded-md px-3 py-2 text-xs font-semibold ${tab === 'facility' ? 'bg-white text-purple-700 shadow-sm' : 'text-slate-600'}`}><Layers className="h-3 w-3" />UB-04 · Facility</button>}</div><div className="flex gap-2"><button disabled={!approved || busy} onClick={() => download('collaboratemd')} className="flex items-center gap-2 rounded-lg bg-emerald-700 px-4 py-2 text-xs font-semibold text-white disabled:opacity-40"><Download className="h-4 w-4" />Download CollaborateMD Excel</button><button disabled={!approved || busy} onClick={() => download('json')} className="rounded-lg border px-3 py-2 text-xs disabled:opacity-40">JSON</button></div></div>
        {split?.warnings.map(w => <p key={w} className="border-b border-amber-100 bg-amber-50 px-4 py-2 text-xs text-amber-800">{w}</p>)}
        <div role="tabpanel" className="overflow-x-auto">{rows.length ? <table className="w-full text-left text-xs"><thead className="bg-slate-100 text-slate-700"><tr>{['DOS', 'Primary DX', 'Secondary DX', ...(tab === 'facility' ? ['Rev code'] : []), 'CPT / HCPCS', 'Modifiers', 'Pointer', 'Units', 'Source justification', 'Status'].map(h => <th key={h} className="whitespace-nowrap p-3">{h}</th>)}</tr></thead><tbody>{rows.map(row => <tr key={row.candidate_id} className="border-t border-slate-200"><td className="p-3">{row.dos}</td><td className="p-3 font-mono">{row.primary_dx || 'Unavailable'}</td><td className="p-3">{row.secondary_dx || '—'}</td>{tab === 'facility' && <td className="p-3 font-mono font-bold text-purple-700">{row.rev_code}</td>}<td className="p-3 font-mono font-bold">{row.cpt}</td><td className="p-3">{row.mod || '—'}</td><td className="p-3">{row.pointer || 'Unavailable'}</td><td className="p-3">{row.units ?? 'Unavailable'}</td><td className="min-w-64 whitespace-pre-wrap p-3 text-slate-600">{row.justification}</td><td className="p-3 text-emerald-700">{split ? 'Review accepted' : 'Code approved; claim fields incomplete'}</td></tr>)}</tbody></table> : <p className="p-6 text-sm text-slate-500">{approved ? tab === 'facility' ? 'No facility lines accepted. Review facility resources and revenue categories above.' : 'No billing lines accepted. ED claims require explicit billing review; the Excel worksheet retains approved codes with unreviewed fields blank.' : 'Claim results appear after code approval and billing review.'}</p>}</div>
        <footer className="border-t border-slate-200 bg-slate-50 p-3 text-xs text-slate-500">{rows.length} {split ? 'reviewed lines' : 'approved code rows'} · Manual-entry worksheet; CollaborateMD import compatibility is not verified.</footer>
      </section>
    </>}
  </div>;
}
