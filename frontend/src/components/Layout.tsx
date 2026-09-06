import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, Clock, AlertTriangle, GitBranch, Map, FileText, MessageCircle } from 'lucide-react';
import clsx from 'clsx';

const navigation = [
  { name: 'Home', href: '/', icon: LayoutDashboard },
  { name: 'Situations', href: '/situations', icon: AlertTriangle },
  { name: 'Decisions', href: '/decisions', icon: GitBranch },
  { name: 'Routes', href: '/routes', icon: Map },
  { name: 'Reports', href: '/reports', icon: FileText },
  { name: 'Ask Move', href: '/ask', icon: MessageCircle },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation();

  return (
    <div className="flex h-screen bg-gray-50">
      <div className="w-72 bg-slate-900 text-white flex flex-col">
        <div className="p-6">
          <h1 className="text-2xl font-bold tracking-wider">MoveIQ</h1>
          <p className="text-slate-400 text-sm mt-1">Decision Intelligence</p>
        </div>
        <nav className="flex-1 px-4 space-y-1">
          {navigation.map((item) => {
            const isActive = location.pathname === item.href || (item.href !== '/' && location.pathname.startsWith(item.href));
            return (
              <Link
                key={item.name}
                to={item.href}
                className={clsx(
                  'flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors',
                  isActive ? 'bg-slate-800 text-white' : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                )}
              >
                <item.icon className="w-5 h-5" />
                {item.name}
              </Link>
            );
          })}
        </nav>
      </div>
      <main className="flex-1 overflow-auto p-8">
        {children}
      </main>
    </div>
  );
}
