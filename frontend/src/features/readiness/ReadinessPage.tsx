import React from 'react';
import { useFetch } from '../../hooks/useFetch';
import { api } from '../../services/api';
import ReadinessGauge from '../../components/ReadinessGauge';
import { Users, AlertCircle } from 'lucide-react';

export default function ReadinessPage() {
  const { data, loading, error } = useFetch(() => api.getReadiness());

  if (loading) return <div className="p-8">Loading readiness...</div>;
  if (error) return <div className="p-8 text-red-500">Error loading data.</div>;
  if (!data) return null;

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      <div>
        <h2 className="text-3xl font-bold text-gray-900">Team Readiness</h2>
        <p className="text-gray-500 mt-1">Shift attendance and at-risk monitoring</p>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {data.map((shift, i) => (
          <div key={i} className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm flex flex-col items-center">
            <h3 className="text-lg font-bold text-gray-900 text-center mb-1">{shift.shift}</h3>
            <p className="text-sm text-gray-500 mb-6">{shift.office} • {shift.direction}</p>
            
            <ReadinessGauge score={shift.readiness_score} baseline={shift.historical_baseline} />
            
            <div className="w-full mt-6 space-y-2 border-t border-gray-100 pt-4">
              <div className="flex justify-between text-sm">
                <span className="text-gray-500 flex items-center gap-1"><Users className="w-4 h-4"/> Expected</span>
                <span className="font-medium text-gray-900">{shift.employees_expected}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-500 flex items-center gap-1"><AlertCircle className="w-4 h-4 text-orange-500"/> At Risk</span>
                <span className="font-medium text-orange-600">{shift.employees_at_risk}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
