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
} from 'lucide-react';
import { api } from '@/lib/api';
import {
  EncounterDetail,
  CodeCandidateItem,
  ClinicalFactItem,
} from '@/lib/types';

export default function ReviewPage() {
  const params = useParams();
  const encounterId = params?.id as string;

  const [encounter, setEncounter] = useState<EncounterDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [activePage, setActivePage] = useState<number>(1);
  const [selectedCandidate, setSelectedCandidate] = useState<CodeCandidateItem | null>(null);
  const [highlightedText, setHighlightedText] = useState<string>('');
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [submittingReview, setSubmittingReview] = useState(false);

  useEffect(() => {
    let ignore = false;
    api.getEncounter(encounterId)
      .then((data) => {
        if (!ignore) {
          setEncounter(data);
          if (data.candidate_codes.length > 0) {
            setSelectedCandidate(data.candidate_codes[0]);
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

  const handleSelectFact = (fact: ClinicalFactItem) => {
    if (fact.evidence) {
      setActivePage(fact.evidence.page_number);
      setHighlightedText(fact.evidence.quoted_text);
    }
  };

  const handleSelectCandidate = (cand: CodeCandidateItem) => {
    setSelectedCandidate(cand);
    if (cand.supporting_evidence.length > 0) {
      setActivePage(cand.supporting_evidence[0].page_number);
      setHighlightedText(cand.supporting_evidence[0].quoted_text);
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

    const approvedIds = encounter.candidate_codes
      .filter((c) => c.status === 'approved' || decision === 'accept')
      .map((c) => c.id);

    try {
      await api.submitReview(
        encounter.id,
        decision,
        `Final review decision: ${decision.toUpperCase()} recorded by certified coder.`,
        approvedIds
      );
      setActionSuccess(`Encounter successfully finalized as ${decision.toUpperCase()}!`);
      const updated = await api.getEncounter(encounter.id);
      setEncounter(updated);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to submit review.';
      alert(msg);
    } finally {
      setSubmittingReview(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[70vh] items-center justify-center">
        <div className="text-xs font-semibold text-slate-500 animate-pulse">
          Loading clinical encounter review workspace...
        </div>
      </div>
    );
  }

  if (!encounter) {
    return (
      <div className="mx-auto max-w-xl py-16 text-center space-y-4">
        <div className="text-sm font-bold text-slate-800">Encounter not found</div>
        <Link href="/encounters" className="text-xs text-blue-600 font-semibold hover:underline">
          &larr; Back to encounters
        </Link>
      </div>
    );
  }

  const currentDoc = encounter.documents[0];
  const pages = currentDoc?.pages || [];
  const activePageObj = pages.find((p) => p.page_number === activePage) || pages[0];
  const fullText = activePageObj?.ocr_text || 'No document text extracted.';

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] overflow-hidden bg-slate-100">
      {/* Top Workflow Bar */}
      <div className="bg-white border-b border-slate-200 px-4 py-2.5 flex items-center justify-between gap-4 shrink-0">
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

          {encounter.status === 'approved' && (
            <div className="flex items-center space-x-1 border-r border-slate-200 pr-2 mr-2">
              <a
                href={api.getExportUrl(encounter.id, 'json')}
                download
                className="inline-flex items-center space-x-1 px-2.5 py-1.5 text-xs font-semibold rounded-md border border-slate-300 bg-white hover:bg-slate-50 text-slate-700"
              >
                <Download className="h-3.5 w-3.5 text-slate-500" />
                <span>JSON</span>
              </a>
              <a
                href={api.getExportUrl(encounter.id, 'csv')}
                download
                className="inline-flex items-center space-x-1 px-2.5 py-1.5 text-xs font-semibold rounded-md border border-slate-300 bg-white hover:bg-slate-50 text-slate-700"
              >
                <Download className="h-3.5 w-3.5 text-slate-500" />
                <span>CSV</span>
              </a>
              <a
                href={api.getExportUrl(encounter.id, 'worksheet')}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center space-x-1 px-2.5 py-1.5 text-xs font-semibold rounded-md border border-blue-600 bg-blue-50 text-blue-700 hover:bg-blue-100"
              >
                <FileText className="h-3.5 w-3.5 text-blue-600" />
                <span>Worksheet</span>
              </a>
            </div>
          )}

          <button
            type="button"
            disabled={submittingReview}
            onClick={() => handleFinalizeReview('accept')}
            className="inline-flex items-center space-x-1.5 rounded-lg bg-emerald-600 px-3.5 py-1.5 text-xs font-bold text-white shadow-xs hover:bg-emerald-700 disabled:opacity-50 transition-colors"
          >
            <CheckCircle2 className="h-4 w-4" />
            <span>Approve &amp; Finalize</span>
          </button>

          <button
            type="button"
            disabled={submittingReview}
            onClick={() => handleFinalizeReview('reject')}
            className="inline-flex items-center space-x-1 rounded-lg border border-red-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-50 disabled:opacity-50 transition-colors"
          >
            <XCircle className="h-3.5 w-3.5" />
            <span>Reject</span>
          </button>
        </div>
      </div>

      {/* Three Column Main Workspace */}
      <div className="grid grid-cols-12 flex-1 overflow-hidden divide-x divide-slate-200">
        {/* COLUMN 1: Medical Record / Document Viewer (4 cols) */}
        <div className="col-span-12 md:col-span-4 flex flex-col bg-white overflow-hidden">
          <div className="border-b border-slate-200 px-4 py-2.5 flex items-center justify-between bg-slate-50 shrink-0">
            <div className="flex items-center space-x-2">
              <FileText className="h-4 w-4 text-blue-600" />
              <span className="text-xs font-bold text-slate-800">
                Medical Record
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

          {/* Text viewer */}
          <div className="flex-1 p-4 overflow-y-auto font-mono text-xs text-slate-800 leading-relaxed bg-slate-50/50 whitespace-pre-wrap select-text">
            {highlightedText ? (
              <div>
                {fullText.split(highlightedText).map((part, i, arr) => (
                  <React.Fragment key={i}>
                    {part}
                    {i < arr.length - 1 && (
                      <mark className="bg-amber-300 text-slate-900 font-semibold px-0.5 rounded-xs">
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

          <div className="p-2 border-t border-slate-200 text-[10px] text-slate-400 text-center bg-white">
            Traceable OCR Document ID: {currentDoc?.id || 'doc-synthetic'}
          </div>
        </div>

        {/* COLUMN 2: Extracted Clinical Facts & Evidence (4 cols) */}
        <div className="col-span-12 md:col-span-4 flex flex-col bg-white overflow-hidden">
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
              encounter.clinical_facts.map((fact) => (
                <div
                  key={fact.id}
                  onClick={() => handleSelectFact(fact)}
                  className="rounded-lg border border-slate-200 bg-slate-50/70 p-3 hover:border-blue-400 hover:bg-blue-50/40 cursor-pointer transition-all space-y-1"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-blue-700 bg-blue-100/60 px-1.5 py-0.5 rounded-xs">
                      {fact.fact_type.replace('_', ' ')}
                    </span>
                    {fact.evidence && (
                      <span className="text-[10px] font-semibold text-slate-400">
                        Page {fact.evidence.page_number}
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
                    <div className="text-[11px] text-slate-600 bg-white border border-slate-200 rounded-sm p-1.5 italic font-sans">
                      &ldquo;{fact.evidence.quoted_text}&rdquo;
                    </div>
                  )}
                </div>
              ))
            )}
          </div>

          <div className="p-2 border-t border-slate-200 text-[10px] text-slate-400 text-center bg-white">
            Click fact to navigate and highlight source evidence
          </div>
        </div>

        {/* COLUMN 3: Candidate Codes, Rules & Review Decisions (4 cols) */}
        <div className="col-span-12 md:col-span-4 flex flex-col bg-white overflow-hidden">
          <div className="border-b border-slate-200 px-4 py-2.5 flex items-center justify-between bg-slate-50 shrink-0">
            <div className="flex items-center space-x-2">
              <Sparkles className="h-4 w-4 text-purple-600" />
              <span className="text-xs font-bold text-slate-800">
                Candidate Codes &amp; Rules
              </span>
            </div>
            <span className="text-[10px] font-bold text-purple-700 bg-purple-100 px-1.5 py-0.5 rounded-sm">
              {encounter.candidate_codes.length} candidates
            </span>
          </div>

          <div className="flex-1 p-3 overflow-y-auto space-y-3">
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
                        {cand.status}
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
                          Deterministic Rule Validations:
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

                    {/* Human Coder Decision Buttons */}
                    <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
                      <div className="flex items-center space-x-1">
                        <button
                          type="button"
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
                          Accept
                        </button>
                        <button
                          type="button"
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
                        Human review required
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          <div className="p-2 border-t border-slate-200 text-[10px] text-slate-400 text-center bg-white flex items-center justify-center space-x-1">
            <ShieldCheck className="h-3.5 w-3.5 text-blue-600" />
            <span>AI proposes &bull; Rules validate &bull; Human approves</span>
          </div>
        </div>
      </div>
    </div>
  );
}
