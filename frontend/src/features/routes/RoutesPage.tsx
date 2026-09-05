import React, { useState } from 'react';
import { useFetch } from '../../hooks/useFetch';
import { api } from '../../services/api';
import { Bus, MapPin, Clock, AlertTriangle, CheckCircle, Zap, Fuel, ArrowUpDown } from 'lucide-react';

export default function RoutesPage() {
  const { data: shifts, loading, error } = useFetch(() => api.getShifts());
  const [selectedShift, setSelectedShift] = useState<string>('ALL');

  if (loading) return <div className="p-8 text-gray-500">Loading route performance...</div>;
  if (error) return <div className="p-8 text-red-500">Error loading routes.</div>;

  const filteredShifts = shifts?.filter(s => selectedShift === 'ALL' || s.shift === selectedShift) || [];

  const totalTrips = shifts?.reduce((sum, s) => sum + s.affected_trips, 0) || 0;
  const avgDelay = shifts && shifts.length > 0 
    ? Math.round((shifts.reduce((sum, s) => sum + (s.avg_delay_minutes || 0), 0) / shifts.length) * 10) / 10 
    : 0;
  const totalAtRisk = shifts?.reduce((sum, s) => sum + s.employees_at_risk, 0) || 0;

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-3xl font-bold text-gray-900">Route & Shift Performance</h2>
          <p className="text-gray-500 mt-1">
            Fleet operations, route punctuality, delay distribution, and vehicle utilization
          </p>
        </div>
        <div className="flex gap-2">
          {['ALL', '03:00', '07:00', '11:00', '15:00', '19:00', '23:00'].map(sh => (
            <button
              key={sh}
              onClick={() => setSelectedShift(sh)}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                selectedShift === sh
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
              }`}
            >
              {sh === 'ALL' ? 'All Shifts' : sh}
            </button>
          ))}
        </div>
      </div>

      {/* KPI Overview */}
      <div className="grid grid-cols-4 gap-6">
        <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Active Routes</p>
            <h3 className="text-2xl font-bold text-gray-900">{totalTrips}</h3>
            <p className="text-xs text-gray-500 mt-1">Operational trips</p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center text-blue-600">
            <Bus className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Avg Route Delay</p>
            <h3 className="text-2xl font-bold text-orange-600">{avgDelay} min</h3>
            <p className="text-xs text-gray-500 mt-1">Across all active bands</p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-orange-50 flex items-center justify-center text-orange-600">
            <Clock className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Delayed Employees</p>
            <h3 className="text-2xl font-bold text-red-600">{totalAtRisk}</h3>
            <p className="text-xs text-gray-500 mt-1">At risk of late arrival</p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-red-50 flex items-center justify-center text-red-600">
            <AlertTriangle className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">EV Fleet Ratio</p>
            <h3 className="text-2xl font-bold text-emerald-600">45.0%</h3>
            <p className="text-xs text-gray-500 mt-1">Zero-emission vehicles</p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-emerald-50 flex items-center justify-center text-emerald-600">
            <Zap className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Shift Cards Grid */}
      <div className="grid grid-cols-3 gap-6">
        {filteredShifts.map((shift, idx) => {
          const score = shift.readiness_score <= 1.0 
            ? Math.round(shift.readiness_score * 1000) / 10 
            : Math.round(shift.readiness_score * 10) / 10;
          const onTimePct = shift.on_time_rate != null ? Math.round(shift.on_time_rate * 100) : score;
          const isAtRisk = score < 85;

          return (
            <div 
              key={idx}
              className={`bg-white rounded-xl border p-5 shadow-sm transition-all hover:shadow-md ${
                isAtRisk ? 'border-orange-200 ring-1 ring-orange-100' : 'border-gray-200'
              }`}
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-lg text-gray-900">{shift.shift}</span>
                  <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded font-medium">
                    {shift.direction}
                  </span>
                </div>
                <span className={`text-sm font-bold ${score >= 85 ? 'text-green-600' : score >= 75 ? 'text-yellow-600' : 'text-red-600'}`}>
                  {score}% Ready
                </span>
              </div>

              <div className="text-xs text-gray-500 mb-4 flex items-center gap-1">
                <MapPin className="w-3.5 h-3.5" />
                <span>{shift.office} • {shift.business_unit}</span>
              </div>

              {/* Progress Bar */}
              <div className="w-full bg-gray-100 rounded-full h-2 mb-4 overflow-hidden">
                <div 
                  className={`h-2 rounded-full transition-all duration-500 ${
                    score >= 85 ? 'bg-green-500' : score >= 75 ? 'bg-yellow-500' : 'bg-red-500'
                  }`}
                  style={{ width: `${Math.min(100, Math.max(5, score))}%` }}
                />
              </div>

              <div className="grid grid-cols-2 gap-3 text-xs border-t border-gray-100 pt-3 text-gray-600">
                <div>
                  <span className="text-gray-400">Trips / Vehicles:</span>
                  <p className="font-semibold text-gray-800 mt-0.5">{shift.affected_trips} cabs</p>
                </div>
                <div>
                  <span className="text-gray-400">On-Time Rate:</span>
                  <p className="font-semibold text-gray-800 mt-0.5">{onTimePct}%</p>
                </div>
                <div>
                  <span className="text-gray-400">Riders Expected:</span>
                  <p className="font-semibold text-gray-800 mt-0.5">{shift.employees_expected} riders</p>
                </div>
                <div>
                  <span className="text-gray-400">At Risk / No-Shows:</span>
                  <p className={`font-semibold mt-0.5 ${shift.employees_at_risk > 0 ? 'text-red-600' : 'text-gray-800'}`}>
                    {shift.employees_at_risk} / {shift.employees_noshow}
                  </p>
                </div>
              </div>

              {shift.top_contributing_situation && (
                <div className="mt-4 pt-3 border-t border-gray-100 text-xs">
                  <span className="text-orange-600 font-medium flex items-center gap-1">
                    <AlertTriangle className="w-3.5 h-3.5" />
                    {shift.top_contributing_situation.replace(/_/g, ' ')}
                  </span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
