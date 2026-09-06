import React from 'react';
import { useFetch } from '../../hooks/useFetch';
import { api } from '../../services/api';
import { FileText, TrendingUp, DollarSign, Award, ShieldAlert, Zap, Download } from 'lucide-react';

export default function ReportsPage() {
  const { data: homeData, loading } = useFetch(() => api.getHome());

  const vendors = [
    { name: 'Vendor Dispatch Desk', trips: 1840, onTime: 82.4, avgDelay: 16.8, p90Delay: 28.0, rating: 4.2, status: 'Review Needed' },
    { name: 'Catalyst South Fleet', trips: 4210, onTime: 94.1, avgDelay: 4.2, p90Delay: 8.5, rating: 4.8, status: 'Optimal' },
    { name: 'Metro Mobility', trips: 3105, onTime: 91.8, avgDelay: 6.1, p90Delay: 11.0, rating: 4.6, status: 'Good' },
    { name: 'Apex Logistics', trips: 2450, onTime: 93.0, avgDelay: 5.4, p90Delay: 9.2, rating: 4.7, status: 'Good' },
  ];

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-3xl font-bold text-gray-900">Executive & Operations Reports</h2>
          <p className="text-gray-500 mt-1">
            Audit-ready intelligence, vendor performance scorecards, and billing transparency
          </p>
        </div>
        <button 
          onClick={() => alert("Report exported to CSV / PDF.")}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700 flex items-center gap-2 shadow-sm"
        >
          <Download className="w-4 h-4" /> Export Executive Summary
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-6">
        <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">SLA Compliance</span>
            <Award className="w-5 h-5 text-blue-600" />
          </div>
          <h3 className="text-3xl font-bold text-gray-900">91.4%</h3>
          <p className="text-xs text-gray-500 mt-1">SLA Target: 90.0% (within 15 min)</p>
        </div>

        <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Avg Cost / KM</span>
            <DollarSign className="w-5 h-5 text-emerald-600" />
          </div>
          <h3 className="text-3xl font-bold text-gray-900">$16.80</h3>
          <p className="text-xs text-emerald-600 font-medium mt-1">-4.2% vs previous quarter</p>
        </div>

        <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Green Fleet Share</span>
            <Zap className="w-5 h-5 text-green-600" />
          </div>
          <h3 className="text-3xl font-bold text-gray-900">45.0%</h3>
          <p className="text-xs text-gray-500 mt-1">Electric vehicle trips</p>
        </div>

        <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Alert Episodes</span>
            <ShieldAlert className="w-5 h-5 text-orange-600" />
          </div>
          <h3 className="text-3xl font-bold text-gray-900">92.8%</h3>
          <p className="text-xs text-gray-500 mt-1">Alert noise compression ratio</p>
        </div>
      </div>

      {/* Vendor Scorecard Table */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="p-6 border-b border-gray-100 flex items-center justify-between">
          <div>
            <h3 className="text-lg font-bold text-gray-900">Vendor Performance & Punctuality Scorecard</h3>
            <p className="text-sm text-gray-500 mt-0.5">Benchmarked over 30-day lookback window</p>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50 text-gray-500 uppercase text-xs">
              <tr>
                <th className="py-3.5 px-6 font-semibold">Vendor Partner</th>
                <th className="py-3.5 px-6 font-semibold">Completed Trips</th>
                <th className="py-3.5 px-6 font-semibold">On-Time %</th>
                <th className="py-3.5 px-6 font-semibold">Avg Delay</th>
                <th className="py-3.5 px-6 font-semibold">P90 Delay</th>
                <th className="py-3.5 px-6 font-semibold">Safety Rating</th>
                <th className="py-3.5 px-6 font-semibold">Operational Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {vendors.map((v, i) => (
                <tr key={i} className="hover:bg-gray-50 transition-colors">
                  <td className="py-4 px-6 font-semibold text-gray-900">{v.name}</td>
                  <td className="py-4 px-6 text-gray-600">{v.trips.toLocaleString()}</td>
                  <td className="py-4 px-6">
                    <span className={`font-bold ${v.onTime >= 92 ? 'text-green-600' : v.onTime >= 85 ? 'text-yellow-600' : 'text-red-600'}`}>
                      {v.onTime}%
                    </span>
                  </td>
                  <td className="py-4 px-6 text-gray-600">{v.avgDelay} min</td>
                  <td className="py-4 px-6 text-gray-600 font-medium">{v.p90Delay} min</td>
                  <td className="py-4 px-6">
                    <span className="inline-flex items-center text-xs font-semibold text-amber-600 bg-amber-50 px-2 py-0.5 rounded">
                      ★ {v.rating} / 5.0
                    </span>
                  </td>
                  <td className="py-4 px-6">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      v.status === 'Optimal' 
                        ? 'bg-green-100 text-green-800' 
                        : v.status === 'Good' 
                        ? 'bg-blue-100 text-blue-800' 
                        : 'bg-red-100 text-red-800'
                    }`}>
                      {v.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
