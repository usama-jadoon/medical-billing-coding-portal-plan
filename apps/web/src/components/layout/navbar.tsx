'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  Activity,
  FileText,
  CheckCircle,
  BookOpen,
  ShieldCheck,
  Settings,
  PlusCircle,
  LogOut,
} from 'lucide-react';
import { getStoredUser, clearAuthSession } from '@/lib/api';
import { User } from '@/lib/types';

export function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      setUser(getStoredUser());
    }, 0);
    return () => clearTimeout(timer);
  }, [pathname]);

  if (pathname === '/login') {
    return null;
  }

  const handleSignOut = () => {
    clearAuthSession();
    router.push('/login');
  };

  const navItems = [
    { label: 'Dashboard', href: '/dashboard', icon: Activity },
    { label: 'Encounters', href: '/encounters', icon: FileText },
    { label: 'Review Queue', href: '/encounters?status=review', icon: CheckCircle },
    { label: 'References', href: '/references', icon: BookOpen },
    { label: 'Audit', href: '/audit', icon: ShieldCheck },
    { label: 'Settings', href: '/settings', icon: Settings },
  ];

  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-200 bg-white shadow-xs">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Brand & Logo */}
        <div className="flex items-center space-x-6">
          <Link href="/dashboard" className="flex items-center space-x-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-600 text-white shadow-xs">
              <Activity className="h-5 w-5" />
            </div>
            <div>
              <div className="text-base font-bold text-slate-900 leading-tight">
                Medical Coding Portal
              </div>
              <div className="text-[10px] font-medium tracking-wide uppercase text-blue-600">
                Human-Reviewed US Coding Assistance
              </div>
            </div>
          </Link>

          {/* Nav Links */}
          <nav className="hidden md:flex items-center space-x-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive =
                item.href === '/dashboard'
                  ? pathname === '/dashboard'
                  : pathname.startsWith(item.href.split('?')[0]);

              return (
                <Link
                  key={item.label}
                  href={item.href}
                  className={`flex items-center space-x-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition-colors ${
                    isActive
                      ? 'bg-blue-50 text-blue-700'
                      : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Right Side CTA and Profile */}
        <div className="flex items-center space-x-3">
          <Link
            href="/encounters/new"
            className="flex items-center space-x-1.5 rounded-lg bg-blue-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-blue-700 transition-colors"
          >
            <PlusCircle className="h-4 w-4" />
            <span>New Encounter</span>
          </Link>

          {user ? (
            <div className="flex items-center space-x-2 border-l border-slate-200 pl-3">
              <div className="text-right hidden sm:block">
                <div className="text-xs font-semibold text-slate-800">{user.email}</div>
                <div className="text-[10px] font-bold text-emerald-600 uppercase tracking-wider">
                  {user.role}
                </div>
              </div>
              <button
                onClick={handleSignOut}
                title="Sign Out"
                className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-md transition-colors"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <Link
              href="/login"
              className="text-xs font-semibold text-slate-700 hover:text-blue-600"
            >
              Sign In
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
