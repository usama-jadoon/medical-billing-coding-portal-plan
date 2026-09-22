'use client';

import React, { useEffect, useState, Suspense } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import {
  Search,
  PlusCircle,
  Filter,
} from 'lucide-react';
import { api } from '@/lib/api';
import { EncounterSummary } from '@/lib/types';

function EncountersContent() {
  const searchParams = useSearchParams();
  const initialStatus = searchParams.get('status') || '';

  const [encounters, setEncounters] = useState<EncounterSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [domainFilter, setDomainFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>(initialStatus);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    let ignore = false;
    api.listEncounters(domainFilter || undefined, statusFilter || undefined)
      .then((data) => {
        if (!ignore) {
          setEncounters(data);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!ignore) {
          setEncounters([]);
          setLoading(false);
        }
      });
    return () => {
      ignore = true;
    };
  }, [domainFilter, statusFilter]);

  const filtered = encounters.filter((e) =>
    e.patient_reference.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Encounters Directory</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Manage clinical records, review candidate codes, and generate approved worksheets.
          </p>
        </div>

        <Link
          href="/encounters/new"
          className="inline-flex items-center space-x-2 rounded-lg bg-blue-600 px-4 py-2 text-xs font-bold text-white shadow-sm hover:bg-blue-700 transition-colors"
        >
          <PlusCircle className="h-4 w-4" />
          <span>New Encounter</span>
        </Link>
      </div>

      {/* Filter Bar */}
      <div className="flex flex-wrap items-center gap-3 bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
        {/* Search */}
        <div className="relative flex-1 min-w-[200px]">
          <Search className="pointer-events-none absolute inset-y-0 left-0 my-auto ml-3 h-4 w-4 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search patient MRN / reference..."
            className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-xs focus:border-blue-600 focus:outline-hidden focus:ring-1 focus:ring-blue-600"
          />
        </div>

        {/* Domain Filter */}
        <div className="flex items-center space-x-2">
          <Filter className="h-4 w-4 text-slate-400" />
          <select
            value={domainFilter}
            onChange={(e) => setDomainFilter(e.target.value)}
            className="rounded-lg border border-slate-300 py-2 px-3 text-xs focus:border-blue-600 focus:outline-hidden focus:ring-1 focus:ring-blue-600 bg-white"
          >
            <option value="">All Coding Domains</option>
            <option value="emergency_department">Emergency Department</option>
            <option value="professional_office">Professional / Office</option>
            <option value="outpatient">Outpatient</option>
            <option value="inpatient">Inpatient</option>
            <option value="surgery">Surgery</option>
            <option value="anesthesia">Anesthesia</option>
            <option value="radiology">Radiology</option>
            <option value="pathology_laboratory">Pathology / Lab</option>
            <option value="behavioral_health">Behavioral Health</option>
            <option value="dental">Dental (CDT)</option>
          </select>
        </div>

        {/* Status Filter */}
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-lg border border-slate-300 py-2 px-3 text-xs focus:border-blue-600 focus:outline-hidden focus:ring-1 focus:ring-blue-600 bg-white"
        >
          <option value="">All Statuses</option>
          <option value="draft">Draft</option>
          <option value="processing">Processing (OCR/Extracting)</option>
          <option value="review">Ready for Review</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
      </div>

      {/* Encounters Table */}
      <div className="rounded-xl border border-slate-200 bg-white shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-500 uppercase tracking-wider font-semibold border-b border-slate-100">
              <tr>
                <th className="px-6 py-3.5">Patient Pseudonym</th>
                <th className="px-6 py-3.5">Date of Service</th>
                <th className="px-6 py-3.5">Domain</th>
                <th className="px-6 py-3.5">Place of Service</th>
                <th className="px-6 py-3.5">Status</th>
                <th className="px-6 py-3.5">Files</th>
                <th className="px-6 py-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={7} className="px-6 py-10 text-center text-slate-400">
                    Loading encounters...
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-10 text-center text-slate-500">
                    No matching encounters found.
                  </td>
                </tr>
              ) : (
                filtered.map((enc) => (
                  <tr key={enc.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="px-6 py-4 font-bold text-slate-900">
                      {enc.patient_reference}
                    </td>
                    <td className="px-6 py-4 text-slate-600 font-medium">
                      {enc.service_date}
                    </td>
                    <td className="px-6 py-4 capitalize text-slate-800 font-medium">
                      {enc.coding_domain.replace('_', ' ')}
                    </td>
                    <td className="px-6 py-4 text-slate-600">
                      POS {enc.place_of_service}
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-block px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                          enc.status === 'approved'
                            ? 'bg-emerald-100 text-emerald-800'
                            : enc.status === 'review'
                            ? 'bg-amber-100 text-amber-800'
                            : enc.status === 'rejected'
                            ? 'bg-red-100 text-red-800'
                            : 'bg-slate-100 text-slate-700'
                        }`}
                      >
                        {enc.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-slate-500">
                      {enc.document_count} file{enc.document_count !== 1 ? 's' : ''}
                    </td>
                    <td className="px-6 py-4 text-right space-x-2">
                      {enc.status === 'draft' ? (
                        <Link
                          href={`/encounters/${enc.id}/upload`}
                          className="font-bold text-blue-600 hover:text-blue-800"
                        >
                          Upload Record &rarr;
                        </Link>
                      ) : (
                        <Link
                          href={`/encounters/${enc.id}/review`}
                          className="font-bold text-blue-600 hover:text-blue-800"
                        >
                          Review &amp; Approve &rarr;
                        </Link>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default function EncountersPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-xs text-slate-500">Loading...</div>}>
      <EncountersContent />
    </Suspense>
  );
}
