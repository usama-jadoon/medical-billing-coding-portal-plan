'use client';

import React, { useEffect, useState } from 'react';
import { Filter, Database } from 'lucide-react';
import { api } from '@/lib/api';
import { AuditEventItem } from '@/lib/types';

export default function AuditPage() {
  const [events, setEvents] = useState<AuditEventItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [eventTypeFilter, setEventTypeFilter] = useState('');

  useEffect(() => {
    let ignore = false;
    api.listAuditEvents(eventTypeFilter || undefined)
      .then((data) => {
        if (!ignore) {
          setEvents(data);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!ignore) {
          setEvents([]);
          setLoading(false);
        }
      });
    return () => {
      ignore = true;
    };
  }, [eventTypeFilter]);

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Immutable Audit Trail</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Append-only security log recording every upload, OCR extraction, code modification, and approval.
          </p>
        </div>
        <div className="flex items-center space-x-1.5 text-xs text-blue-700 bg-blue-50 border border-blue-200 px-3 py-1.5 rounded-lg">
          <Database className="h-4 w-4" />
          <span className="font-semibold">Tenant-Scoped Audit</span>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex items-center justify-between bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs">
        <div className="flex items-center space-x-2">
          <Filter className="h-4 w-4 text-slate-400" />
          <span className="text-xs font-semibold text-slate-600">Filter Event:</span>
          <select
            value={eventTypeFilter}
            onChange={(e) => setEventTypeFilter(e.target.value)}
            className="rounded-lg border border-slate-300 py-1.5 px-3 text-xs focus:border-blue-600 focus:outline-hidden bg-white"
          >
            <option value="">All Audit Events</option>
            <option value="user_login">User Login</option>
            <option value="encounter_created">Encounter Created</option>
            <option value="document_uploaded">Document Uploaded</option>
            <option value="pipeline_processed">Pipeline Processed</option>
            <option value="review_accept">Review Accepted</option>
            <option value="review_reject">Review Rejected</option>
            <option value="encounter_exported_json">Export JSON</option>
            <option value="encounter_exported_csv">Export CSV</option>
          </select>
        </div>

        <span className="text-xs text-slate-500 font-medium">
          Showing {events.length} records
        </span>
      </div>

      {/* Audit Log Table */}
      <div className="rounded-xl border border-slate-200 bg-white shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-500 uppercase tracking-wider font-semibold border-b border-slate-100">
              <tr>
                <th className="px-6 py-3">Timestamp (UTC)</th>
                <th className="px-6 py-3">Actor ID</th>
                <th className="px-6 py-3">Event Action</th>
                <th className="px-6 py-3">Entity Type</th>
                <th className="px-6 py-3">Entity ID</th>
                <th className="px-6 py-3">Metadata (PHI-Sanitized)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-mono">
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-6 py-10 text-center text-slate-400 font-sans">
                    Loading audit trail...
                  </td>
                </tr>
              ) : events.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-10 text-center text-slate-500 font-sans">
                    No audit records logged yet.
                  </td>
                </tr>
              ) : (
                events.map((ev) => (
                  <tr key={ev.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="px-6 py-3.5 text-slate-600 whitespace-nowrap">
                      {ev.created_at.replace('T', ' ').slice(0, 19)}
                    </td>
                    <td className="px-6 py-3.5 text-slate-800 font-semibold">
                      {ev.actor_id}
                    </td>
                    <td className="px-6 py-3.5">
                      <span className="inline-block px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-slate-100 text-slate-800 font-sans">
                        {ev.event_type}
                      </span>
                    </td>
                    <td className="px-6 py-3.5 text-slate-600 uppercase text-[11px] font-sans">
                      {ev.entity_type}
                    </td>
                    <td className="px-6 py-3.5 text-slate-500 text-[11px]">
                      {ev.entity_id}
                    </td>
                    <td className="px-6 py-3.5 text-slate-600 text-[11px] max-w-xs truncate">
                      {JSON.stringify(ev.metadata)}
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
