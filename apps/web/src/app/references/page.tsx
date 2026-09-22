'use client';

import React, { useEffect, useState } from 'react';
import { BookOpen, ExternalLink, ShieldCheck } from 'lucide-react';
import { api } from '@/lib/api';
import { ReferenceItem } from '@/lib/types';

export default function ReferencesPage() {
  const [references, setReferences] = useState<ReferenceItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.listReferences()
      .then(setReferences)
      .catch(() => setReferences([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Official Reference Center</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Authoritative US government &amp; code-set owner repositories, guidelines, and licensing standards.
          </p>
        </div>
        <div className="flex items-center space-x-1.5 text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 px-3 py-1.5 rounded-lg">
          <ShieldCheck className="h-4 w-4" />
          <span className="font-semibold">Zero-Scraping Compliance</span>
        </div>
      </div>

      <div className="rounded-xl border border-blue-200 bg-blue-50/60 p-4 text-xs text-blue-900 space-y-1">
        <div className="font-bold flex items-center space-x-1.5">
          <BookOpen className="h-4 w-4 text-blue-600" />
          <span>Licensing &amp; Authorship Hierarchy</span>
        </div>
        <p className="text-[11px] text-blue-800 leading-relaxed">
          The portal distinguishes official government releases from proprietary code-set owners (AMA CPT, ADA CDT).
          In compliance with US federal copyright law, proprietary datasets are accessed through verified licensing adapters or direct outbound official links, never through unauthorized scraping.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {loading ? (
          <div className="col-span-2 text-center py-12 text-xs text-slate-400">
            Loading official reference catalog...
          </div>
        ) : (
          references.map((ref) => (
            <div
              key={ref.id}
              className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs flex flex-col justify-between space-y-4 hover:border-blue-300 transition-colors"
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span
                    className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${
                      ref.category === 'Government'
                        ? 'bg-blue-100 text-blue-800'
                        : 'bg-purple-100 text-purple-800'
                    }`}
                  >
                    {ref.category}
                  </span>
                  <span className="text-[10px] font-mono text-slate-400">
                    Verified {ref.last_verified}
                  </span>
                </div>

                <h3 className="text-sm font-bold text-slate-900">{ref.name}</h3>

                <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-600 bg-slate-50 p-2.5 rounded-lg border border-slate-100 font-medium">
                  <div>
                    <span className="text-slate-400">System:</span> {ref.code_system}
                  </div>
                  <div>
                    <span className="text-slate-400">Version:</span> {ref.version}
                  </div>
                  <div>
                    <span className="text-slate-400">Effective:</span> {ref.effective_date}
                  </div>
                  <div>
                    <span className="text-slate-400">Official:</span> Yes
                  </div>
                </div>

                {ref.notes && (
                  <p className="text-xs text-slate-500 leading-relaxed">{ref.notes}</p>
                )}
              </div>

              <div className="pt-3 border-t border-slate-100 flex items-center justify-between">
                <span className="text-[11px] text-slate-400">Direct Portal Reference</span>
                <a
                  href={ref.official_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center space-x-1.5 text-xs font-bold text-blue-600 hover:text-blue-800 hover:underline"
                >
                  <span>Open Official Source</span>
                  <ExternalLink className="h-3.5 w-3.5" />
                </a>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
