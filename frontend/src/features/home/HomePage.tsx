import React from 'react';
import { useFetch } from '../../hooks/useFetch';
import { api } from '../../services/api';
import SituationCard from '../../components/SituationCard';
import ReadinessGauge from '../../components/ReadinessGauge';

export default function HomePage() {
  const { data, loading, error } = useFetch(() => api.getHome(), [], 5000);

  if (loading) return <div className="p-8 text-gray-500">Loading Command Center...</div>;
  if (error) return <div className="p-8 text-red-500">Error loading dashboard data.</div>;
  if (!data) return null;

  const overallScore = data.stats.overall_readiness <= 1.0 
    ? Math.round(data.stats.overall_readiness * 1000) / 10 
    : Math.round(data.stats.overall_readiness * 10) / 10;

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      <div>
        <h2 className="text-3xl font-bold text-gray-900">Command Center</h2>
        <p className="text-gray-500 mt-1">Real-time mobility intelligence and active risk intervention</p>
      </div>

      <div className="grid grid-cols-4 gap-6">
        <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Overall Readiness</p>
            <h3 className="text-3xl font-bold text-gray-900">{overallScore}%</h3>
            <p className="text-xs text-gray-500 mt-1">{data.stats.employees_at_risk} employees at risk</p>
          </div>
          <div className="flex-shrink-0">
            <ReadinessGauge score={data.stats.overall_readiness} compact={true} />
          </div>
        </div>
        <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Active Situations</p>
          <h3 className={`text-3xl font-bold ${data.stats.active_situations > 0 ? 'text-red-600' : 'text-green-600'}`}>
            {data.stats.active_situations}
          </h3>
          <p className="text-xs text-gray-500 mt-1">Requiring intervention</p>
        </div>
        <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Total Trips</p>
          <h3 className="text-3xl font-bold text-gray-900">{data.stats.total_trips.toLocaleString()}</h3>
          <p className="text-xs text-gray-500 mt-1">Operational routes</p>
        </div>
        <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Total Employees</p>
          <h3 className="text-3xl font-bold text-gray-900">{data.stats.total_employees.toLocaleString()}</h3>
          <p className="text-xs text-gray-500 mt-1">Riders scheduled</p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-8">
        <div className="col-span-2 space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="text-xl font-bold text-gray-900">Situations Requiring Attention</h3>
            <span className="text-sm font-medium text-gray-500">
              {data.active_situations.length} active {data.active_situations.length === 1 ? 'situation' : 'situations'}
            </span>
          </div>
          <div className="space-y-4">
            {data.active_situations.map(sit => (
              <SituationCard key={sit.situation_id} situation={sit} />
            ))}
            {data.active_situations.length === 0 && (
              <div className="p-8 text-center text-gray-500 bg-white rounded-lg border border-gray-200">
                No active situations detected. All routes operating within SLAs.
              </div>
            )}
          </div>
        </div>
        
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="text-xl font-bold text-gray-900">Shift Readiness</h3>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4 space-y-4">
            {data.readiness_summary.map((shift, i) => {
              const shiftPct = shift.readiness_score <= 1.0 
                ? Math.round(shift.readiness_score * 1000) / 10 
                : Math.round(shift.readiness_score * 10) / 10;
              const colorClass = shiftPct >= 85 ? 'text-green-600' : shiftPct >= 75 ? 'text-yellow-600' : 'text-red-600';
              
              return (
                <div key={i} className="flex items-center justify-between border-b last:border-0 pb-4 last:pb-0 border-gray-100">
                  <div>
                    <div className="font-semibold text-gray-900">{shift.shift}</div>
                    <div className="text-xs text-gray-500">{shift.office} • {shift.direction}</div>
                  </div>
                  <div className="text-right">
                    <div className={`font-bold text-lg ${colorClass}`}>
                      {shiftPct}%
                    </div>
                    <div className="text-xs text-gray-500">
                      {shift.employees_at_risk > 0 ? `${shift.employees_at_risk} at risk` : 'On track'}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
