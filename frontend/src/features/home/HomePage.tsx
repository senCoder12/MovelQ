import React, { useState } from 'react';
import { Siren } from 'lucide-react';
import { useFetch } from '../../hooks/useFetch';
import { api } from '../../services/api';
import SituationCard from '../../components/SituationCard';
import ReadinessGauge from '../../components/ReadinessGauge';
import SimulateAlertModal from '../../components/SimulateAlertModal';
import ReadinessByBusinessUnitChart from '../../components/ReadinessByBusinessUnitChart';
import SituationsByPriorityChart from '../../components/SituationsByPriorityChart';
import AtRiskShiftsList from '../../components/AtRiskShiftsList';
import { SituationPriority } from '../../types';

export default function HomePage() {
  const { data, loading, error } = useFetch(() => api.getHome(), [], 5000);
  const [showSimulate, setShowSimulate] = useState(false);
  const [priorityFilter, setPriorityFilter] = useState<SituationPriority | null>(null);

  if (loading) return <div className="p-8 text-gray-500">Loading Command Center...</div>;
  if (error) return <div className="p-8 text-red-500">Error loading dashboard data.</div>;
  if (!data) return null;

  const overallScore = data.stats.overall_readiness <= 1.0
    ? Math.round(data.stats.overall_readiness * 1000) / 10
    : Math.round(data.stats.overall_readiness * 10) / 10;

  const visibleSituations = priorityFilter
    ? data.active_situations.filter(s => s.priority === priorityFilter)
    : data.active_situations;

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-3xl font-bold text-gray-900">Command Center</h2>
          <p className="text-gray-500 mt-1">Real-time mobility intelligence and active risk intervention</p>
        </div>
        <button
          onClick={() => setShowSimulate(true)}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md bg-red-600 text-white hover:bg-red-700 transition-colors"
        >
          <Siren className="w-4 h-4" />
          Simulate Alert
        </button>
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

      <div className="grid grid-cols-2 gap-6">
        <ReadinessByBusinessUnitChart data={data.readiness_summary} />
        <SituationsByPriorityChart
          situations={data.active_situations}
          selected={priorityFilter}
          onSelect={setPriorityFilter}
        />
      </div>

      <AtRiskShiftsList data={data.readiness_summary} />

      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h3 className="text-xl font-bold text-gray-900">Situations Requiring Attention</h3>
          <div className="flex items-center gap-3">
            {priorityFilter && (
              <button
                onClick={() => setPriorityFilter(null)}
                className="text-xs font-medium text-blue-600 hover:text-blue-800"
              >
                Clear "{priorityFilter}" filter
              </button>
            )}
            <span className="text-sm font-medium text-gray-500">
              {visibleSituations.length} {visibleSituations.length === 1 ? 'situation' : 'situations'}
            </span>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          {visibleSituations.map(sit => (
            <SituationCard key={sit.situation_id} situation={sit} />
          ))}
          {visibleSituations.length === 0 && (
            <div className="col-span-2 p-8 text-center text-gray-500 bg-white rounded-lg border border-gray-200">
              {priorityFilter
                ? `No ${priorityFilter} situations detected.`
                : 'No active situations detected. All routes operating within SLAs.'}
            </div>
          )}
        </div>
      </div>

      {showSimulate && <SimulateAlertModal onClose={() => setShowSimulate(false)} />}
    </div>
  );
}
