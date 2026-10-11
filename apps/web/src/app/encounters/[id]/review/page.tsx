'use client';

import React, { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  CheckCircle2,
  XCircle,
  Download,
  ShieldCheck,
  FileText,
  Bookmark,
  Sparkles,
  ChevronLeft,
  ChevronRight,
  HelpCircle,
  FileQuestion,
  Layers,
  Crosshair,
  ShieldAlert,
} from 'lucide-react';
import { api } from '@/lib/api';
import {
  EncounterDetail,
  CodeCandidateItem,
  ClinicalFactItem,
  EvidenceItem,
} from '@/lib/types';

export default function ReviewPage() {
  const params = useParams();
  const encounterId = params?.id as string;

  const [encounter, setEncounter] = useState<EncounterDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [activePage, setActivePage] = useState<number>(1);
  const [selectedCandidate, setSelectedCandidate] = useState<CodeCandidateItem | null>(null);
  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceItem | null>(null);
  const [highlightedText, setHighlightedText] = useState<string>('');
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [submittingReview, setSubmittingReview] = useState(false);
  const [notes, setNotes] = useState('');
  const [actionError, setActionError] = useState<string | null>(null);
  const [activeDocumentId, setActiveDocumentId] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    api.getEncounter(encounterId)
      .then((data) => {
        if (!ignore) {
          setEncounter(data);
          if (data.candidate_codes.length > 0) {
            setSelectedCandidate(data.candidate_codes[0]);
            if (data.candidate_codes[0].supporting_evidence.length > 0) {
              const ev = data.candidate_codes[0].supporting_evidence[0];
              setSelectedEvidence(ev);
              setActivePage(ev.page_number);
              setHighlightedText(ev.quoted_text);
            }
          }
          setLoading(false);
        }
      })
      .catch(() => {
        if (!ignore) {
          setLoading(false);
        }
      });
    return () => {
      ignore = true;
    };
  }, [encounterId]);

  const processingStatus = encounter?.status;
  useEffect(() => {
    if (!processingStatus || !['ingesting', 'ocr_ready', 'facts_ready', 'candidates_ready', 'validated'].includes(processingStatus)) return;
    const timer = setInterval(() => {
      api.getEncounter(encounterId).then(setEncounter).catch(err => setActionError(err.message));
    }, 2000);
    return () => clearInterval(timer);
  }, [processingStatus, encounterId]);

  const handleSelectFact = (fact: ClinicalFactItem) => {
    if (fact.evidence) {
      setSelectedEvidence(fact.evidence);
      setActiveDocumentId(fact.evidence.document_id || null);
      setActivePage(fact.evidence.page_number);
      setHighlightedText(fact.evidence.quoted_text);
    }
  };

  const handleSelectCandidate = (cand: CodeCandidateItem) => {
    setSelectedCandidate(cand);
    if (cand.supporting_evidence.length > 0) {
      const ev = cand.supporting_evidence[0];
      setSelectedEvidence(ev);
      setActiveDocumentId(ev.document_id || null);
      setActivePage(ev.page_number);
      setHighlightedText(ev.quoted_text);
    }
  };

  const handleCandidateDecision = (candId: string, newStatus: 'approved' | 'rejected' | 'candidate') => {
    if (!encounter) return;
    const updatedCandidates = encounter.candidate_codes.map((c) =>
      c.id === candId ? { ...c, status: newStatus } : c
    );
    setEncounter({ ...encounter, candidate_codes: updatedCandidates });
    if (selectedCandidate && selectedCandidate.id === candId) {
      setSelectedCandidate({ ...selectedCandidate, status: newStatus });
    }
  };

  const handleFinalizeReview = async (decision: 'accept' | 'reject' | 'request_documentation' | 'mark_uncertain') => {
    if (!encounter) return;
    setSubmittingReview(true);
    setActionSuccess(null);
    setActionError(null);

    const approvedIds = encounter.candidate_codes
      .filter((c) => c.status === 'approved')
      .map((c) => c.id);

    try {
      await api.submitReview(
        encounter.id,
        decision,
        notes,
        approvedIds,
        encounter.version
      );
      setActionSuccess(`Case successfully recorded as ${decision.toUpperCase()}!`);
      const updated = await api.getEncounter(encounter.id);
      setEncounter(updated);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to submit review.';
      setActionError(msg);
    } finally {
      setSubmittingReview(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[70vh] items-center justify-center">
        <div className="text-xs font-semibold text-slate-500 animate-pulse">
          Loading clinical encounter review workbench...
        </div>
      </div>
    );
  }

  if (!encounter) {
    return (
      <div className="mx-auto max-w-xl py-16 text-center space-y-4">
        <div className="text-sm font-bold text-slate-800">Encounter not found</div>
        <Link href="/encounters" className="text-xs text-blue-600 font-semibold hover:underline">
          &larr; Back to cases
        </Link>
      </div>
    );
  }

  const currentDoc = encounter.documents.find(d => d.id === activeDocumentId || d.id === selectedEvidence?.document_id) || encounter.documents[encounter.documents.length - 1];
  const pages = currentDoc?.pages || [];
  const activePageObj = pages.find((p) => p.page_number === activePage) || pages[0];
  const fullText = activePageObj?.ocr_text || 'No document text extracted.';
  const selectedCount = encounter.candidate_codes.filter(c => c.status === 'approved').length;
  const canReview = ['review', 'review_required', 'validated'].includes(encounter.status);
  const hasSelectedBlocker = (encounter.validation_findings || []).some(f =>
    f.severity === 'BLOCK' && f.candidate_id && encounter.candidate_codes.some(c => c.id === f.candidate_id && c.status === 'approved')
  );
  const handleExport = async (format: 'json' | 'csv' | 'worksheet' | 'manifest') => {
    setActionError(null);
    try {
      if (format === 'manifest') await api.downloadManifest(encounter.id);
      else await api.downloadExport(encounter.id, format);
      setEncounter(await api.getEncounter(encounter.id));
    } catch (err) { setActionError(err instanceof Error ? err.message : 'Export failed.'); }
  };

  // 8 Stages definition for visual audit summary
  const validationStages = [
    { id: '1_catalog', name: '1. Catalog', desc: 'Code exists in active release' },
    { id: '2_effective_date', name: '2. Effective Date', desc: 'Active for DOS' },
    { id: '3_evidence', name: '3. Evidence', desc: 'Facts have source links' },
    { id: '4_documentation', name: '4. Documentation', desc: 'Required elements present' },
    { id: '5_relationships', name: '5. Relationships', desc: 'Mutual exclusions & bundling' },
    { id: '6_modifiers', name: '6. Modifiers', desc: 'Modifier applicability & evidence' },
    { id: '7_ncci', name: '7. NCCI Edits', desc: 'CMS Procedure-to-Procedure' },
    { id: '8_approval_gate', name: '8. Approval Gate', desc: 'Owner authority check' },
  ];

  return (
    <div className="flex flex-col min-h-[calc(100vh-4rem)] md:h-[calc(100vh-4rem)] md:overflow-hidden bg-slate-100">
      {/* Top Workflow Bar */}
      <div className="bg-white border-b border-slate-200 px-4 py-2.5 flex flex-wrap items-center justify-between gap-4 shrink-0">
        <div className="flex items-center space-x-3">
          <Link
            href="/encounters"
            className="p-1 rounded-md hover:bg-slate-100 text-slate-500 hover:text-slate-800 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-sm font-bold text-slate-900">{encounter.patient_reference}</span>
              <span
                className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                  encounter.status === 'approved'
                    ? 'bg-emerald-100 text-emerald-800'
                    : encounter.status === 'review'
                    ? 'bg-amber-100 text-amber-800'
                    : 'bg-slate-100 text-slate-700'
                }`}
              >
                {encounter.status}
              </span>
            </div>
            <div className="text-[11px] text-slate-500">
              DOS: {encounter.service_date} &bull; Domain: <span className="capitalize font-semibold text-slate-700">{encounter.coding_domain.replace('_', ' ')}</span> &bull; POS: {encounter.place_of_service}
            </div>
          </div>
        </div>

        {/* Action Controls & Export Buttons */}
        <div className="flex items-center space-x-2">
          {actionSuccess && (
            <span className="text-[11px] font-bold text-emerald-600 mr-2 flex items-center space-x-1">
              <CheckCircle2 className="h-3.5 w-3.5" />
              <span>{actionSuccess}</span>
            </span>
          )}

          {['approved', 'exported'].includes(encounter.status) && (
            <div className="flex items-center space-x-1 border-r border-slate-200 pr-2 mr-2">
              <button
                onClick={() => handleExport('json')}
                className="inline-flex items-center space-x-1 px-2.5 py-1.5 text-xs font-semibold rounded-md border border-slate-300 bg-white hover:bg-slate-50 text-slate-700"
              >
                <Download className="h-3.5 w-3.5 text-slate-500" />
                <span>JSON</span>
              </button>
              <button
                onClick={() => handleExport('csv')}
                className="inline-flex items-center space-x-1 px-2.5 py-1.5 text-xs font-semibold rounded-md border border-slate-300 bg-white hover:bg-slate-50 text-slate-700"
              >
                <Download className="h-3.5 w-3.5 text-slate-500" />
                <span>CSV</span>
              </button>
              <button
                onClick={() => handleExport('worksheet')}
                className="inline-flex items-center space-x-1 px-2.5 py-1.5 text-xs font-semibold rounded-md border border-blue-600 bg-blue-50 text-blue-700 hover:bg-blue-100"
              >
                <FileText className="h-3.5 w-3.5 text-blue-600" />
                <span>Worksheet</span>
              </button>
              <button onClick={() => handleExport('manifest')} className="px-2 py-1.5 text-xs font-semibold text-blue-700">Signed manifest</button>
            </div>
          )}

          {/* Owner Decision Actions */}
          <button
            type="button"
            disabled={submittingReview || !canReview || selectedCount === 0 || hasSelectedBlocker}
            onClick={() => handleFinalizeReview('accept')}
            className="inline-flex items-center space-x-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-bold text-white shadow-xs hover:bg-emerald-700 disabled:opacity-50 transition-colors"
          >
            <CheckCircle2 className="h-3.5 w-3.5" />
            <span>Approve selected ({selectedCount})</span>
          </button>

          <button
            type="button"
            disabled={submittingReview || !canReview}
            onClick={() => handleFinalizeReview('request_documentation')}
            className="inline-flex items-center space-x-1 rounded-lg border border-amber-300 bg-white px-2 py-1.5 text-xs font-semibold text-amber-700 hover:bg-amber-50 disabled:opacity-50 transition-colors"
          >
            <FileQuestion className="h-3.5 w-3.5" />
            <span>Request Docs</span>
          </button>

          <button
            type="button"
            disabled={submittingReview || !canReview}
            onClick={() => handleFinalizeReview('mark_uncertain')}
            className="inline-flex items-center space-x-1 rounded-lg border border-purple-300 bg-white px-2 py-1.5 text-xs font-semibold text-purple-700 hover:bg-purple-50 disabled:opacity-50 transition-colors"
          >
            <HelpCircle className="h-3.5 w-3.5" />
            <span>Uncertain</span>
          </button>

          <button
            type="button"
            disabled={submittingReview || !canReview}
            onClick={() => handleFinalizeReview('reject')}
            className="inline-flex items-center space-x-1 rounded-lg border border-red-300 bg-white px-2 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-50 disabled:opacity-50 transition-colors"
          >
            <XCircle className="h-3.5 w-3.5" />
            <span>Reject</span>
          </button>
        </div>
      </div>

      <div className="bg-white border-b border-slate-200 px-4 py-2 flex flex-wrap gap-3 items-center shrink-0">
        <label className="text-xs text-slate-600 flex-1">Review notes
          <input aria-label="Review notes" value={notes} onChange={e => setNotes(e.target.value)} placeholder="Record your reasoning or missing documentation" className="ml-2 border border-slate-300 rounded-md px-2 py-1 w-full sm:w-96" />
        </label>
        <span className="text-[11px] text-slate-500">Development catalogs · Human review required · Version {encounter.version}</span>
        <Link href={`/encounters/${encounter.id}/upload`} className="text-xs text-blue-700">Upload amended record</Link>
        {actionError && <p role="alert" className="w-full text-xs text-red-700">{actionError}</p>}
      </div>

      {/* Three Column Main Workspace */}
      <div className="grid grid-cols-12 md:flex-1 md:min-h-0 md:overflow-hidden divide-x divide-slate-200">
        {/* COLUMN 1: Medical Record / Document Viewer (4 cols) */}
        <div className="col-span-12 md:col-span-4 flex flex-col bg-white min-h-[26rem] md:min-h-0 overflow-hidden">
          <div className="border-b border-slate-200 px-4 py-2.5 flex items-center justify-between bg-slate-50 shrink-0">
            <div className="flex items-center space-x-2">
              <FileText className="h-4 w-4 text-blue-600" />
              <span className="text-xs font-bold text-slate-800">
                Source Document &bull; Provenance
              </span>
            </div>

            {/* Page navigation */}
            {pages.length > 1 && (
              <div className="flex items-center space-x-1 text-xs text-slate-600">
                <button
                  disabled={activePage <= 1}
                  onClick={() => setActivePage((p) => Math.max(1, p - 1))}
                  className="p-1 hover:bg-slate-200 rounded-sm disabled:opacity-30"
                >
                  <ChevronLeft className="h-3.5 w-3.5" />
                </button>
                <span className="text-[11px] font-semibold">
                  Page {activePage} of {pages.length}
                </span>
                <button
                  disabled={activePage >= pages.length}
                  onClick={() => setActivePage((p) => Math.min(pages.length, p + 1))}
                  className="p-1 hover:bg-slate-200 rounded-sm disabled:opacity-30"
                >
                  <ChevronRight className="h-3.5 w-3.5" />
                </button>
              </div>
            )}
          </div>

          {encounter.documents.length > 0 && <select aria-label="Source document" value={currentDoc?.id || ''} onChange={e => { setActiveDocumentId(e.target.value); setActivePage(1); setSelectedEvidence(null); setHighlightedText(''); }} className="text-xs border-b border-slate-200 p-2 bg-white">
            {encounter.documents.map(doc => <option key={doc.id} value={doc.id}>{doc.filename}</option>)}
          </select>}

          {/* Traceable Bounding Box / Region Coordinate HUD */}
          {selectedEvidence && (
            <div className="bg-amber-50/80 border-b border-amber-200 px-3 py-1.5 flex items-center justify-between text-[11px] text-amber-900 shrink-0">
              <div className="flex items-center space-x-1.5">
                <Crosshair className="h-3.5 w-3.5 text-amber-700" />
                <span className="font-semibold">Region Anchor:</span>
                <span className="font-mono text-[10px] bg-white px-1 py-0.5 rounded-xs border border-amber-300">
                  {selectedEvidence.region_id ? selectedEvidence.region_id.slice(0, 8) + '...' : 'P' + selectedEvidence.page_number}
                </span>
                <span className="text-[10px] text-amber-800">
                  {selectedEvidence.bbox ? `bbox [${Math.round(selectedEvidence.bbox.x * 100)}%, ${Math.round(selectedEvidence.bbox.y * 100)}%]` : `Text span ${selectedEvidence.start_offset}–${selectedEvidence.end_offset}`}
                </span>
              </div>
              <span className="text-[10px] font-bold text-emerald-800 bg-emerald-100 px-1.5 py-0.2 rounded-xs">
                {selectedEvidence.evidence_role || 'SUPPORT'}
              </span>
            </div>
          )}

          {/* Text viewer */}
          <div className="flex-1 p-4 overflow-y-auto font-mono text-xs text-slate-800 leading-relaxed bg-slate-50/50 whitespace-pre-wrap select-text relative">
            {highlightedText ? (
              <div>
                {fullText.split(highlightedText).map((part, i, arr) => (
                  <React.Fragment key={i}>
                    {part}
                    {i < arr.length - 1 && (
                      <mark className="bg-amber-300 text-slate-900 font-semibold px-0.5 rounded-xs shadow-xs border border-amber-400">
                        {highlightedText}
                      </mark>
                    )}
                  </React.Fragment>
                ))}
              </div>
            ) : (
              fullText
            )}
          </div>

          <div className="p-2 border-t border-slate-200 text-[10px] text-slate-500 text-center bg-white flex items-center justify-between px-3">
            <span>Doc SHA-256: {currentDoc?.sha256 ? currentDoc.sha256.slice(0, 12) + '...' : 'Unavailable'}</span>
            <span className="text-slate-400">Section 5 Lineage Pin</span>
          </div>
        </div>

        {/* COLUMN 2: Extracted Clinical Facts & Evidence (4 cols) */}
        <div className="col-span-12 md:col-span-4 flex flex-col bg-white min-h-[26rem] md:min-h-0 overflow-hidden">
          <div className="border-b border-slate-200 px-4 py-2.5 flex items-center justify-between bg-slate-50 shrink-0">
            <div className="flex items-center space-x-2">
              <Bookmark className="h-4 w-4 text-emerald-600" />
              <span className="text-xs font-bold text-slate-800">
                Extracted Clinical Facts
              </span>
            </div>
            <span className="text-[10px] font-bold text-slate-500 bg-slate-200 px-1.5 py-0.5 rounded-sm">
              {encounter.clinical_facts.length} facts
            </span>
          </div>

          <div className="flex-1 p-3 overflow-y-auto space-y-2.5">
            {encounter.clinical_facts.length === 0 ? (
              <div className="text-center py-10 text-xs text-slate-400">
                No clinical facts extracted yet.
              </div>
            ) : (
              encounter.clinical_facts.map((fact) => {
                const isSelected = selectedEvidence?.quoted_text === fact.evidence?.quoted_text;
                return (
                  <div
                    key={fact.id}
                    onClick={() => handleSelectFact(fact)}
                    className={`rounded-lg border p-3 cursor-pointer transition-all space-y-1.5 ${
                      isSelected
                        ? 'border-blue-500 bg-blue-50/50 shadow-xs'
                        : 'border-slate-200 bg-slate-50/70 hover:border-blue-300 hover:bg-blue-50/30'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-blue-700 bg-blue-100/60 px-1.5 py-0.5 rounded-xs">
                        {fact.fact_type.replace('_', ' ')}
                      </span>
                      {fact.evidence && (
                        <span className="text-[10px] font-semibold text-slate-400 flex items-center space-x-1">
                          <Crosshair className="h-3 w-3 text-slate-400" />
                          <span>Page {fact.evidence.page_number}</span>
                        </span>
                      )}
                    </div>

                    <div className="text-xs font-semibold text-slate-900">
                      {String(
                        fact.value.condition ||
                        fact.value.procedure_name ||
                        fact.value.complaint ||
                        fact.value.mdm_level ||
                        fact.value.symptom ||
                        fact.value.pos_description ||
                        fact.value.service_date ||
                        JSON.stringify(fact.value)
                      )}
                    </div>

                    {fact.evidence && (
                      <div className="text-[11px] text-slate-600 bg-white border border-slate-200 rounded-sm p-1.5 italic font-sans flex items-start space-x-1">
                        <span>&ldquo;{fact.evidence.quoted_text}&rdquo;</span>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>

          <div className="p-2 border-t border-slate-200 text-[10px] text-slate-400 text-center bg-white">
            Select fact to navigate and highlight region coordinate anchors
          </div>
        </div>

        {/* COLUMN 3: Candidate Codes, 8-Stage Rules & Review (4 cols) */}
        <div className="col-span-12 md:col-span-4 flex flex-col bg-white min-h-[26rem] md:min-h-0 overflow-hidden">
          <div className="border-b border-slate-200 px-4 py-2.5 flex items-center justify-between bg-slate-50 shrink-0">
            <div className="flex items-center space-x-2">
              <Sparkles className="h-4 w-4 text-purple-600" />
              <span className="text-xs font-bold text-slate-800">
                Candidates &bull; 8-Stage Rules
              </span>
            </div>
            <span className="text-[10px] font-bold text-purple-700 bg-purple-100 px-1.5 py-0.5 rounded-sm">
              {encounter.candidate_codes.length} candidates
            </span>
          </div>

          <div className="flex-1 p-3 overflow-y-auto space-y-3">
            {/* 8-Stage Deterministic Validation Summary Card */}
            <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-slate-800 flex items-center space-x-1">
                  <Layers className="h-3.5 w-3.5 text-blue-600" />
                  <span>8-Stage Validation Pipeline</span>
                </span>
                <span className="text-[10px] font-bold bg-emerald-100 text-emerald-800 px-1.5 py-0.5 rounded-full">
                  Deterministic
                </span>
              </div>

              <div className="grid grid-cols-2 gap-1.5 text-[10px]">
                {validationStages.map((stg) => (
                  <div key={stg.id} className="bg-white border border-slate-200 rounded-md p-1.5 flex items-center space-x-1">
                    {(encounter.validation_findings || []).some(f => f.stage === stg.id && f.severity === 'BLOCK') ? <ShieldAlert className="h-3 w-3 text-red-600 shrink-0" /> : <HelpCircle className="h-3 w-3 text-slate-400 shrink-0" />}
                    <span className="font-semibold text-slate-700 truncate">{stg.name}</span>
                  </div>
                ))}
              </div>
              {(encounter.validation_findings || []).map(finding => <div key={finding.id} className={`text-[11px] rounded-md p-2 ${finding.severity === 'BLOCK' ? 'bg-red-50 text-red-800' : finding.severity === 'INFO' ? 'bg-blue-50 text-blue-800' : 'bg-amber-50 text-amber-800'}`}>
                <strong>{finding.severity} · {finding.stage.replaceAll('_', ' ')}</strong><p>{finding.message}</p>
              </div>)}
            </div>

            {/* Candidates */}
            {encounter.candidate_codes.length === 0 ? (
              <div className="text-center py-10 text-xs text-slate-400">
                No code candidates generated.
              </div>
            ) : (
              encounter.candidate_codes.map((cand) => {
                const isSelected = selectedCandidate?.id === cand.id;
                return (
                  <div
                    key={cand.id}
                    onClick={() => handleSelectCandidate(cand)}
                    className={`rounded-xl border p-3.5 transition-all cursor-pointer space-y-2.5 ${
                      isSelected
                        ? 'border-blue-600 bg-blue-50/20 shadow-xs ring-1 ring-blue-600'
                        : 'border-slate-200 bg-white hover:border-slate-300'
                    }`}
                  >
                    {/* Header: Code & System */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <span className="font-mono text-sm font-bold text-slate-900">
                          {cand.code}
                        </span>
                        <span className="text-[10px] font-bold uppercase tracking-wider bg-slate-100 text-slate-700 px-1.5 py-0.5 rounded-sm">
                          {cand.code_system} &bull; {cand.code_version}
                        </span>
                      </div>

                      <span
                        className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${
                          cand.status === 'approved'
                            ? 'bg-emerald-100 text-emerald-800'
                            : cand.status === 'rejected'
                            ? 'bg-red-100 text-red-800'
                            : 'bg-amber-100 text-amber-800'
                        }`}
                      >
                        {canReview && cand.status === 'approved' ? 'selected' : cand.status}
                      </span>
                    </div>

                    {/* Rationale */}
                    <p className="text-xs text-slate-600 leading-snug">
                      {cand.rationale}
                    </p>

                    {/* Rule Results */}
                    {cand.rule_results && cand.rule_results.length > 0 && (
                      <div className="space-y-1 pt-1 border-t border-slate-100">
                        <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                          Deterministic Findings:
                        </div>
                        {cand.rule_results.map((rr, idx) => (
                          <div
                            key={idx}
                            className={`flex items-start space-x-1.5 text-[11px] p-1.5 rounded-md ${
                              rr.status === 'PASS'
                                ? 'bg-emerald-50 text-emerald-900 border border-emerald-100'
                                : rr.status === 'WARNING'
                                ? 'bg-amber-50 text-amber-900 border border-amber-100'
                                : 'bg-red-50 text-red-900 border border-red-100'
                            }`}
                          >
                            <span className="font-bold text-[9px] uppercase px-1 py-0.2 rounded-xs bg-white/70">
                              {rr.status}
                            </span>
                            <span className="leading-tight">{rr.message}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Owner Action Buttons */}
                    <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
                      <div className="flex items-center space-x-1">
                        <button
                          type="button"
                          disabled={!canReview || submittingReview}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleCandidateDecision(cand.id, 'approved');
                          }}
                          className={`px-2 py-1 text-[11px] font-bold rounded-md transition-colors ${
                            cand.status === 'approved'
                              ? 'bg-emerald-600 text-white'
                              : 'bg-slate-100 text-slate-700 hover:bg-emerald-100 hover:text-emerald-800'
                          }`}
                        >
                          Select
                        </button>
                        <button
                          type="button"
                          disabled={!canReview || submittingReview}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleCandidateDecision(cand.id, 'rejected');
                          }}
                          className={`px-2 py-1 text-[11px] font-bold rounded-md transition-colors ${
                            cand.status === 'rejected'
                              ? 'bg-red-600 text-white'
                              : 'bg-slate-100 text-slate-700 hover:bg-red-100 hover:text-red-800'
                          }`}
                        >
                          Reject
                        </button>
                      </div>

                      <span className="text-[10px] text-slate-400 font-medium">
                        Owner Authority Gate
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          <div className="p-2 border-t border-slate-200 text-[10px] text-slate-500 text-center bg-white flex items-center justify-center space-x-1">
            <ShieldCheck className="h-3.5 w-3.5 text-blue-600" />
            <span>AI proposes &bull; Rules validate &bull; Authenticated owner decides</span>
          </div>
        </div>
      </div>
    </div>
  );
}
