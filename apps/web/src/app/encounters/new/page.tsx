'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft, ArrowRight, ShieldAlert, Building, Calendar, Hash } from 'lucide-react';
import Link from 'next/link';
import { api } from '@/lib/api';

const CODING_DOMAINS = [
  { id: 'emergency_department', name: 'Emergency Department', defaultPos: '23', desc: 'Emergency E/M, trauma, acute urgent care' },
  { id: 'professional_office', name: 'Professional / Office', defaultPos: '11', desc: 'Outpatient clinic, established/new patient E/M' },
];

export default function NewEncounterPage() {
  const router = useRouter();
  const [domain, setDomain] = useState('emergency_department');
  const [patientRef, setPatientRef] = useState('');
  const [serviceDate, setServiceDate] = useState('');
  const [pos, setPos] = useState('23');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDomainChange = (newDomain: string) => {
    setDomain(newDomain);
    const found = CODING_DOMAINS.find((d) => d.id === newDomain);
    if (found) {
      setPos(found.defaultPos);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await api.createEncounter({
        patient_reference: patientRef.trim(),
        service_date: serviceDate.trim(),
        coding_domain: domain,
        place_of_service: pos.trim(),
      });
      // Direct forward to document upload step
      router.push(`/encounters/${res.id}/upload`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to create encounter.';
      setError(msg);
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:px-8 space-y-6">
      <div className="flex items-center space-x-3">
        <Link
          href="/encounters"
          className="p-1.5 rounded-md hover:bg-slate-100 text-slate-500 hover:text-slate-800 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Initiate New Coding Encounter</h1>
          <p className="text-xs text-slate-500">
            Step 1 of 2: Select coding domain and input patient pseudonymous reference.
          </p>
        </div>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 p-3 text-xs text-red-700 border border-red-200">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Domain Selection Grid */}
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-xs space-y-4">
          <label className="block text-xs font-bold uppercase tracking-wider text-slate-700">
            1. Select Coding Domain
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {CODING_DOMAINS.map((d) => (
              <button
                key={d.id}
                type="button"
                onClick={() => handleDomainChange(d.id)}
                className={`p-3.5 rounded-lg border text-left transition-all ${
                  domain === d.id
                    ? 'border-blue-600 bg-blue-50/70 shadow-xs ring-1 ring-blue-600'
                    : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-xs font-bold ${domain === d.id ? 'text-blue-900' : 'text-slate-900'}`}>
                    {d.name}
                  </span>
                  <span className="text-[10px] font-semibold text-slate-400">
                    POS {d.defaultPos}
                  </span>
                </div>
                <p className="text-[11px] text-slate-500 mt-1">{d.desc}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Encounter Metadata */}
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-xs space-y-4">
          <label className="block text-xs font-bold uppercase tracking-wider text-slate-700">
            2. Encounter Details &amp; Privacy
          </label>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700">
                Patient Pseudonymous ID
              </label>
              <div className="relative mt-1">
                <Hash className="pointer-events-none absolute inset-y-0 left-0 my-auto ml-3 h-4 w-4 text-slate-400" />
                <input
                  type="text"
                  required
                  value={patientRef}
                  onChange={(e) => setPatientRef(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-xs focus:border-blue-600 focus:outline-hidden focus:ring-1 focus:ring-blue-600"
                  placeholder="e.g. SYNTH-90210"
                />
              </div>
              <p className="text-[10px] text-slate-400 mt-1">
                Do not enter full patient names or SSNs.
              </p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700">
                Date of Service
              </label>
              <div className="relative mt-1">
                <Calendar className="pointer-events-none absolute inset-y-0 left-0 my-auto ml-3 h-4 w-4 text-slate-400" />
                <input
                  type="date"
                  required
                  value={serviceDate}
                  onChange={(e) => setServiceDate(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-xs focus:border-blue-600 focus:outline-hidden focus:ring-1 focus:ring-blue-600"
                />
              </div>
              <p className="text-[10px] text-slate-400 mt-1">
                Determines active code set fiscal year.
              </p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700">
                Place of Service (POS)
              </label>
              <div className="relative mt-1">
                <Building className="pointer-events-none absolute inset-y-0 left-0 my-auto ml-3 h-4 w-4 text-slate-400" />
                <input
                  type="text"
                  required
                  value={pos}
                  onChange={(e) => setPos(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-xs focus:border-blue-600 focus:outline-hidden focus:ring-1 focus:ring-blue-600"
                  placeholder="e.g. 23 or 11"
                />
              </div>
              <p className="text-[10px] text-slate-400 mt-1">
                CMS POS Code (23=ED, 11=Office)
              </p>
            </div>
          </div>
        </div>

        {/* Submit */}
        <div className="flex items-center justify-between pt-2">
          <div className="flex items-center space-x-1.5 text-xs text-slate-500">
            <ShieldAlert className="h-4 w-4 text-emerald-600" />
            <span>Development workspace · Use synthetic records.</span>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="inline-flex items-center space-x-2 rounded-lg bg-blue-600 px-5 py-2.5 text-xs font-bold text-white shadow-sm hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            <span>{loading ? 'Creating...' : 'Continue to Document Upload'}</span>
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </form>
    </div>
  );
}
