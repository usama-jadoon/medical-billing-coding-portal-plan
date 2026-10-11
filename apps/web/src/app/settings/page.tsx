'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { Shield, Fingerprint, Database, Layers } from 'lucide-react';

type Capabilities = {
  mode: string; storage: string; ocr: string; queue: string; catalog: string; ruleset: string;
  owner_restricted: boolean; mfa_configured: boolean; session_minutes: number; step_up_seconds: number;
};

export default function SettingsPage() {
  const [config, setConfig] = useState<Capabilities | null>(null);
  const [error, setError] = useState('');
  const [email, setEmail] = useState('');
  useEffect(() => {
    Promise.all([api.getCapabilities(), api.getMe()]).then(([capabilities, user]) => {
      setConfig(capabilities); setEmail(user.email);
    }).catch(err => setError(err.message));
  }, []);
  return <div className="mx-auto max-w-5xl px-6 py-10 space-y-6">
    <div><p className="text-xs uppercase tracking-widest text-blue-600 font-semibold">Workspace configuration</p>
      <h1 className="text-2xl font-bold mt-2">Settings & policy</h1>
      <p className="text-sm text-slate-500 mt-2">Runtime controls and the policy used by your evidence workflow.</p></div>
    {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
    {!config ? <p className="text-sm text-slate-500">Loading configuration...</p> : <>
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-900">Synthetic development mode. Sample catalogs and rules are active. Production processing is disabled.</div>
      <div className="grid md:grid-cols-2 gap-5">
        {[{icon: Fingerprint, title: 'Owner & session', rows: [
          ['Signed-in account', email], ['Named owner restriction', config.owner_restricted ? 'Enabled' : 'Not configured'],
          ['Authenticator MFA', config.mfa_configured ? 'Enabled' : 'Not configured'],
          ['Session lifetime', `${config.session_minutes} minutes`], ['Approval / export sign-in freshness', `${config.step_up_seconds / 60} minutes`],
        ]}, {icon: Database, title: 'Processing', rows: [
          ['Storage adapter', config.storage], ['Text extraction', config.ocr], ['Worker delivery', config.queue],
          ['Image and scanned PDF OCR', 'Adapter required'],
        ]}, {icon: Layers, title: 'Versioned policy', rows: [
          ['Catalog', config.catalog], ['Ruleset', config.ruleset], ['Active profiles', 'Emergency department; Professional / Office'],
          ['Full NCCI policy package', 'Not configured'],
        ]}, {icon: Shield, title: 'Review controls', rows: [
          ['Evidence', 'Exact source spans and document hashes'], ['Source changes', 'New snapshot; approval invalidated'],
          ['Export', 'Approved candidates only; policy rechecked'], ['Manifest', 'HMAC-SHA256 integrity signature'],
        ]}].map(card => <section key={card.title} className="bg-white border border-slate-200 rounded-xl p-6">
          <h2 className="font-semibold flex items-center gap-2 mb-4"><card.icon size={18} className="text-blue-600" />{card.title}</h2>
          <dl className="space-y-3">{card.rows.map(([label, value]) => <div key={label} className="flex justify-between gap-6 text-xs"><dt className="text-slate-500">{label}</dt><dd className="font-medium text-right">{value}</dd></div>)}</dl>
        </section>)}
      </div>
    </>}
  </div>;
}
