'use client';

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  UploadCloud,
  FileText,
  ArrowLeft,
  AlertCircle,
  ShieldCheck,
  Sparkles,
  ArrowRight,
} from 'lucide-react';
import { api } from '@/lib/api';
import { EncounterDetail } from '@/lib/types';

export default function DocumentUploadPage() {
  const params = useParams();
  const router = useRouter();
  const encounterId = params?.id as string;

  const [encounter, setEncounter] = useState<EncounterDetail | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [pipelineStep, setPipelineStep] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (encounterId) {
      api.getEncounter(encounterId).then(setEncounter).catch(() => {});
    }
  }, [encounterId]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleUseSynthetic = () => {
    const syntheticText = `METROPOLITAN HEALTH EMERGENCY DEPARTMENT
EMERGENCY ENCOUNTER RECORD (SYNTHETIC RECORD - NO REAL PHI)

Date of Service: ${encounter?.service_date || '2026-09-22'}
Place of Service: Emergency Department (POS 23)
Attending Physician: Dr. Jane Doe, MD
Patient Pseudonymous ID: ${encounter?.patient_reference || 'SYNTH-90210'}

CHIEF COMPLAINT:
Severe right lower quadrant pain and nausea x 12 hours.

ASSESSMENT & DOCUMENTED DIAGNOSIS:
1. Acute appendicitis (unspecified)
2. Right lower quadrant pain

MEDICAL DECISION MAKING:
High complexity decision making. Life-threatening surgical abdomen requiring emergent surgical consult.

PLAN & INTERVENTIONS:
- Emergent General Surgery consult obtained.
- Patient scheduled for Laparoscopic appendectomy.

Electronically Signed By: Dr. Jane Doe, MD (2026-09-22 14:30)`;

    const syntheticFile = new File([syntheticText], 'synthetic-er-record.txt', {
      type: 'text/plain',
    });
    setFile(syntheticFile);
    setError(null);
  };

  const handleUpload = async () => {
    if (!file) {
      setError('Please select or load a clinical document first.');
      return;
    }

    setUploading(true);
    setError(null);
    setPipelineStep('Validating file signature & hashing (SHA-256)...');

    try {
      setPipelineStep('Uploading record and preparing evidence...');

      await api.uploadDocument(encounterId, file);

      // Once finished, jump directly into review workspace!
      router.push(`/encounters/${encounterId}/review`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Document upload and processing failed.';
      setError(msg);
      setUploading(false);
      setPipelineStep(null);
    }
  };

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6 lg:px-8 space-y-6">
      <div className="flex items-center space-x-3">
        <Link
          href={`/encounters`}
          className="p-1.5 rounded-md hover:bg-slate-100 text-slate-500 hover:text-slate-800 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Upload Clinical Document</h1>
          <p className="text-xs text-slate-500">
            Step 2 of 2: Upload source medical record for OCR, clinical fact extraction, and rule evaluation.
          </p>
        </div>
      </div>

      {encounter && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 text-xs flex flex-wrap items-center justify-between gap-2 shadow-xs">
          <div>
            <span className="text-slate-400">Patient:</span>{' '}
            <span className="font-bold text-slate-800">{encounter.patient_reference}</span>
          </div>
          <div>
            <span className="text-slate-400">DOS:</span>{' '}
            <span className="font-bold text-slate-800">{encounter.service_date}</span>
          </div>
          <div>
            <span className="text-slate-400">Domain:</span>{' '}
            <span className="font-bold text-blue-600 capitalize">
              {encounter.coding_domain.replace('_', ' ')}
            </span>
          </div>
          <div>
            <span className="text-slate-400">POS:</span>{' '}
            <span className="font-bold text-slate-800">{encounter.place_of_service}</span>
          </div>
        </div>
      )}

      {error && (
        <div className="rounded-lg bg-red-50 p-3 text-xs text-red-700 border border-red-200 flex items-start space-x-2">
          <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white p-8 shadow-xs space-y-6 text-center">
        {/* Dropzone */}
        <label
          htmlFor="file-upload"
          className="group block cursor-pointer rounded-xl border-2 border-dashed border-slate-300 p-8 hover:border-blue-500 hover:bg-blue-50/30 transition-all"
        >
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-blue-50 text-blue-600 group-hover:scale-105 transition-transform">
            <UploadCloud className="h-7 w-7" />
          </div>
          <div className="mt-3 text-sm font-bold text-slate-800">
            Click to select a clinical document
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Searchable PDF or UTF-8 text · Maximum 25MB. Scans and images require an OCR adapter.
          </p>
          <input
            id="file-upload"
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,.tiff,.tif,.txt"
            onChange={handleFileChange}
            className="hidden"
          />
        </label>

        {/* Selected file card */}
        {file && (
          <div className="rounded-lg border border-blue-200 bg-blue-50/50 p-4 text-left flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <FileText className="h-6 w-6 text-blue-600 shrink-0" />
              <div>
                <div className="text-xs font-bold text-slate-900">{file.name}</div>
                <div className="text-[11px] text-slate-500">
                  {(file.size / 1024).toFixed(1)} KB &bull; {file.type || 'Plain Text'}
                </div>
              </div>
            </div>
            <span className="text-[10px] font-bold text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded-full">
              Ready
            </span>
          </div>
        )}

        {/* Synthetic Load Shortcut */}
        <div className="flex items-center justify-center">
          <button
            type="button"
            onClick={handleUseSynthetic}
            className="inline-flex items-center space-x-1.5 rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100 hover:text-slate-900 transition-colors"
          >
            <Sparkles className="h-3.5 w-3.5 text-blue-600" />
            <span>Load Sample Emergency Department Record (Synthetic)</span>
          </button>
        </div>

        {/* Processing State */}
        {uploading && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-xs text-amber-900 space-y-2">
            <div className="font-bold flex items-center justify-center space-x-2">
              <div className="h-3 w-3 rounded-full border-2 border-amber-600 border-t-transparent animate-spin" />
              <span>Processing Medical Record Pipeline...</span>
            </div>
            <div className="text-[11px] text-amber-700">{pipelineStep}</div>
          </div>
        )}

        {/* Action Button */}
        <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
          <div className="flex items-center space-x-1.5 text-[11px] text-slate-500 text-left">
            <ShieldCheck className="h-4 w-4 text-emerald-600 shrink-0" />
            <span>Immutable source &bull; Verified source hashes &bull; Human review required</span>
          </div>

          <button
            type="button"
            disabled={!file || uploading}
            onClick={handleUpload}
            className="inline-flex items-center space-x-2 rounded-lg bg-blue-600 px-5 py-2.5 text-xs font-bold text-white shadow-sm hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            <span>{uploading ? 'Processing...' : 'Upload & Run Coding Pipeline'}</span>
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
