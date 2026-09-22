'use client';

import React, { useEffect, useState } from 'react';
import { Shield, Building, CheckCircle2 } from 'lucide-react';
import { getStoredUser } from '@/lib/api';
import { User as UserType } from '@/lib/types';

export default function SettingsPage() {
  const [user, setUser] = useState<UserType | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      setUser(getStoredUser());
    }, 0);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:px-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">System &amp; Tenant Settings</h1>
        <p className="text-xs text-slate-500 mt-0.5">
          Tenant organization profile, RBAC authorization, and HIPAA compliance policies.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* User & Org Profile Card */}
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-xs space-y-4">
          <div className="flex items-center space-x-2 border-b border-slate-100 pb-3">
            <Building className="h-5 w-5 text-blue-600" />
            <h2 className="text-sm font-bold text-slate-900">Tenant Identity</h2>
          </div>

          <div className="space-y-3 text-xs">
            <div>
              <span className="text-slate-400 block font-medium">Organization ID:</span>
              <span className="font-mono text-slate-800 font-semibold">{user?.organization_id || 'org-1-uuid'}</span>
            </div>
            <div>
              <span className="text-slate-400 block font-medium">Authenticated Account:</span>
              <span className="text-slate-800 font-semibold">{user?.email || 'coder@apexhealth.org'}</span>
            </div>
            <div>
              <span className="text-slate-400 block font-medium">Active RBAC Role:</span>
              <span className="inline-block mt-0.5 px-2 py-0.5 text-[10px] font-bold uppercase rounded-md bg-emerald-100 text-emerald-800">
                {user?.role || 'Coder'}
              </span>
            </div>
          </div>
        </div>

        {/* Security Controls Card */}
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-xs space-y-4">
          <div className="flex items-center space-x-2 border-b border-slate-100 pb-3">
            <Shield className="h-5 w-5 text-emerald-600" />
            <h2 className="text-sm font-bold text-slate-900">Security &amp; HIPAA Controls</h2>
          </div>

          <div className="space-y-2.5 text-xs text-slate-600">
            <div className="flex items-center space-x-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
              <span>Zero-Trust Organization Scoping on every database query</span>
            </div>
            <div className="flex items-center space-x-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
              <span>Client-submitted organization_id rejected server-side</span>
            </div>
            <div className="flex items-center space-x-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
              <span>Magic byte verification &amp; SHA-256 integrity validation</span>
            </div>
            <div className="flex items-center space-x-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
              <span>Prompt injection defense for uploaded clinical records</span>
            </div>
            <div className="flex items-center space-x-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
              <span>PHI-sanitized structured application logging</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
