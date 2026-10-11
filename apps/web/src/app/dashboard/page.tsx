'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  FileText,
  Clock,
  CheckCircle2,
  AlertTriangle,
  PlusCircle,
  ArrowRight,
  Shield,
  BookOpen,
} from 'lucide-react';
import { api } from '@/lib/api';
import { EncounterSummary } from '@/lib/types';

export default function DashboardPage() {
  const [encounters, setEncounters] = useState<EncounterSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let ignore = false;
    api.listEncounters()
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
  }, []);

  const reviewCount = encounters.filter((e) => ['review', 'review_required'].includes(e.status)).length;
  const approvedCount = encounters.filter((e) => ['approved', 'exported'].includes(e.status)).length;
  const draftCount = encounters.filter((e) => ['draft', 'created', 'ingesting'].includes(e.status)).length;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8 space-y-8">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            Clinical Coding Operations
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Overview of encounters, clinical fact extractions, and human review queues.
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

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500">Total Encounters</span>
            <FileText className="h-4 w-4 text-blue-600" />
          </div>
          <div className="mt-2 text-2xl font-extrabold text-slate-900">{encounters.length}</div>
          <div className="text-[11px] text-slate-500 mt-1">Tenant-scoped records</div>
        </div>

        <div className="rounded-xl border border-amber-200 bg-amber-50/60 p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-amber-800">Awaiting Human Review</span>
            <Clock className="h-4 w-4 text-amber-600" />
          </div>
          <div className="mt-2 text-2xl font-extrabold text-amber-900">{reviewCount}</div>
          <div className="text-[11px] text-amber-700 mt-1">Coder decision required</div>
        </div>

        <div className="rounded-xl border border-emerald-200 bg-emerald-50/60 p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-emerald-800">Approved Worksheets</span>
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
          </div>
          <div className="mt-2 text-2xl font-extrabold text-emerald-900">{approvedCount}</div>
          <div className="text-[11px] text-emerald-700 mt-1">Verified &amp; export ready</div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500">Drafts / Ingestion</span>
            <AlertTriangle className="h-4 w-4 text-slate-400" />
          </div>
          <div className="mt-2 text-2xl font-extrabold text-slate-900">{draftCount}</div>
          <div className="text-[11px] text-slate-500 mt-1">Document upload pending</div>
        </div>
      </div>

      {/* Review Queue Callout Banner if items await review */}
      {reviewCount > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-xs">
          <div className="flex items-center space-x-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-amber-200 text-amber-800">
              <Clock className="h-4 w-4" />
            </div>
            <div>
              <div className="text-xs font-bold text-amber-900">
                {reviewCount} Encounter{reviewCount > 1 ? 's' : ''} Ready in Review Queue
              </div>
              <div className="text-[11px] text-amber-700">
                Proposed candidates are linked to evidence and waiting for your review.
              </div>
            </div>
          </div>

          <Link
            href="/encounters?status=review_required"
            className="inline-flex items-center space-x-1 text-xs font-bold text-amber-900 hover:text-amber-950 underline"
          >
            <span>Open Review Queue</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      )}

      {/* Recent Encounters Table */}
      <div className="rounded-xl border border-slate-200 bg-white shadow-xs overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h2 className="text-sm font-bold text-slate-900">Recent Clinical Encounters</h2>
          <Link
            href="/encounters"
            className="text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center space-x-1"
          >
            <span>View All</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-500 uppercase tracking-wider font-semibold border-b border-slate-100">
              <tr>
                <th className="px-6 py-3">Patient Reference</th>
                <th className="px-6 py-3">Service Date</th>
                <th className="px-6 py-3">Coding Domain</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3">Documents</th>
                <th className="px-6 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-slate-400">
                    Loading encounters...
                  </td>
                </tr>
              ) : encounters.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-slate-500">
                    No encounters created yet. Click{' '}
                    <Link href="/encounters/new" className="text-blue-600 font-bold hover:underline">
                      New Encounter
                    </Link>{' '}
                    to begin.
                  </td>
                </tr>
              ) : (
                encounters.slice(0, 5).map((enc) => (
                  <tr key={enc.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="px-6 py-3.5 font-bold text-slate-900">
                      {enc.patient_reference}
                    </td>
                    <td className="px-6 py-3.5 text-slate-600">
                      {enc.service_date}
                    </td>
                    <td className="px-6 py-3.5 capitalize text-slate-700 font-medium">
                      {enc.coding_domain.replace('_', ' ')}
                    </td>
                    <td className="px-6 py-3.5">
                      <span
                        className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
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
                    <td className="px-6 py-3.5 text-slate-500">
                      {enc.document_count} file{enc.document_count !== 1 ? 's' : ''}
                    </td>
                    <td className="px-6 py-3.5 text-right">
                      {enc.status === 'draft' ? (
                        <Link
                          href={`/encounters/${enc.id}/upload`}
                          className="font-semibold text-blue-600 hover:text-blue-700"
                        >
                          Upload Record &rarr;
                        </Link>
                      ) : (
                        <Link
                          href={`/encounters/${enc.id}/review`}
                          className="font-semibold text-blue-600 hover:text-blue-700"
                        >
                          Review Codes &rarr;
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

      {/* Security & Reference Quick Links */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Link
          href="/references"
          className="rounded-xl border border-slate-200 bg-white p-5 hover:border-blue-300 hover:shadow-xs transition-all flex items-center space-x-4"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
            <BookOpen className="h-5 w-5" />
          </div>
          <div>
            <div className="text-xs font-bold text-slate-900">Official Reference Center</div>
            <div className="text-[11px] text-slate-500">
              CMS, CDC, AMA CPT, and ADA CDT official licensed sources and guidelines.
            </div>
          </div>
        </Link>

        <Link
          href="/audit"
          className="rounded-xl border border-slate-200 bg-white p-5 hover:border-emerald-300 hover:shadow-xs transition-all flex items-center space-x-4"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
            <Shield className="h-5 w-5" />
          </div>
          <div>
            <div className="text-xs font-bold text-slate-900">Immutable Audit Trail</div>
            <div className="text-[11px] text-slate-500">
              Complete chronological tracking of all extractions, modifications, and approvals.
            </div>
          </div>
        </Link>
      </div>
    </div>
  );
}
