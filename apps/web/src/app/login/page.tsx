'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Activity, Shield, Lock, Mail, Building, ArrowRight, AlertCircle } from 'lucide-react';
import { api, setAuthSession } from '@/lib/api';

export default function LoginPage() {
  const router = useRouter();
  const [isRegister, setIsRegister] = useState(false);
  const [orgName, setOrgName] = useState('Apex Health Systems');
  const [email, setEmail] = useState('coder@apexhealth.org');
  const [password, setPassword] = useState('CoderPassword123!');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      let res;
      if (isRegister) {
        res = await api.register(orgName, email, password);
      } else {
        res = await api.login(email, password);
      }
      setAuthSession(res.access_token, res.user);
      router.push('/dashboard');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Authentication failed. Please check credentials.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const setTestAccount = (userEmail: string, userPass: string) => {
    setEmail(userEmail);
    setPassword(userPass);
    setIsRegister(false);
    setError(null);
  };

  return (
    <div className="flex min-h-screen flex-col justify-center py-12 sm:px-6 lg:px-8 bg-slate-100">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-blue-600 text-white shadow-md">
          <Activity className="h-7 w-7" />
        </div>
        <h2 className="mt-4 text-2xl font-bold tracking-tight text-slate-900">
          Medical Billing &amp; Coding Portal
        </h2>
        <p className="mt-1 text-xs text-slate-600">
          Secure, Auditable, Human-Reviewed US Coding Assistance
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-6 shadow-sm rounded-xl border border-slate-200 sm:px-10">
          <div className="flex border-b border-slate-200 mb-6">
            <button
              type="button"
              onClick={() => { setIsRegister(false); setError(null); }}
              className={`pb-3 text-xs font-semibold flex-1 text-center transition-colors border-b-2 ${
                !isRegister
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => { setIsRegister(true); setError(null); }}
              className={`pb-3 text-xs font-semibold flex-1 text-center transition-colors border-b-2 ${
                isRegister
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              Register Organization
            </button>
          </div>

          {error && (
            <div className="mb-4 flex items-start space-x-2 rounded-lg bg-red-50 p-3 text-xs text-red-700 border border-red-200">
              <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {isRegister && (
              <div>
                <label className="block text-xs font-semibold text-slate-700">
                  Organization Name
                </label>
                <div className="relative mt-1">
                  <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                    <Building className="h-4 w-4" />
                  </div>
                  <input
                    type="text"
                    required
                    value={orgName}
                    onChange={(e) => setOrgName(e.target.value)}
                    className="block w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-xs focus:border-blue-600 focus:outline-hidden focus:ring-1 focus:ring-blue-600"
                    placeholder="e.g. Apex Health Systems"
                  />
                </div>
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold text-slate-700">
                Email Address
              </label>
              <div className="relative mt-1">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                  <Mail className="h-4 w-4" />
                </div>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="block w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-xs focus:border-blue-600 focus:outline-hidden focus:ring-1 focus:ring-blue-600"
                  placeholder="name@organization.com"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700">
                Password
              </label>
              <div className="relative mt-1">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                  <Lock className="h-4 w-4" />
                </div>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="block w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-xs focus:border-blue-600 focus:outline-hidden focus:ring-1 focus:ring-blue-600"
                  placeholder="••••••••"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="flex w-full items-center justify-center space-x-2 rounded-lg bg-blue-600 py-2.5 px-4 text-xs font-bold text-white shadow-sm hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              <span>{loading ? 'Authenticating...' : isRegister ? 'Create Organization' : 'Sign In'}</span>
              <ArrowRight className="h-4 w-4" />
            </button>
          </form>

          {/* Preset test credentials helper */}
          <div className="mt-6 border-t border-slate-200 pt-4">
            <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-2">
              Preset Test Accounts:
            </div>
            <div className="grid grid-cols-3 gap-2">
              <button
                type="button"
                onClick={() => setTestAccount('coder@apexhealth.org', 'CoderPassword123!')}
                className="rounded-md border border-slate-200 bg-slate-50 p-2 text-left hover:border-blue-400 hover:bg-blue-50 transition-colors"
              >
                <div className="text-[11px] font-bold text-slate-800">Coder</div>
                <div className="text-[10px] text-slate-500">Apex Health</div>
              </button>

              <button
                type="button"
                onClick={() => setTestAccount('reviewer@apexhealth.org', 'ReviewerPassword123!')}
                className="rounded-md border border-slate-200 bg-slate-50 p-2 text-left hover:border-emerald-400 hover:bg-emerald-50 transition-colors"
              >
                <div className="text-[11px] font-bold text-slate-800">Reviewer</div>
                <div className="text-[10px] text-slate-500">Approvals</div>
              </button>

              <button
                type="button"
                onClick={() => setTestAccount('readonly@apexhealth.org', 'ReadOnlyPassword123!')}
                className="rounded-md border border-slate-200 bg-slate-50 p-2 text-left hover:border-slate-400 hover:bg-slate-100 transition-colors"
              >
                <div className="text-[11px] font-bold text-slate-800">Read-Only</div>
                <div className="text-[10px] text-slate-500">Auditor</div>
              </button>
            </div>
          </div>

          <div className="mt-4 flex items-center justify-center space-x-1.5 text-[11px] text-slate-500">
            <Shield className="h-3.5 w-3.5 text-emerald-600" />
            <span>Strict Tenant Isolation &bull; Append-Only Audit</span>
          </div>
        </div>
      </div>
    </div>
  );
}
