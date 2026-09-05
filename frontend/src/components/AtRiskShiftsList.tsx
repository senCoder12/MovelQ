import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { ShiftReadiness } from '../types';

function toPct(v: number | null | undefined) {
  if (v == null) return null;
  return v <= 1.0 ? Math.round(v * 1000) / 10 : Math.round(v * 10) / 10;
}

const MAX_ROWS = 8;

export default function AtRiskShiftsList({ data }: { data: ShiftReadiness[] }) {
  const worst = data
    .filter(r => r.employees_expected > 0)
    .slice()
    .sort((a, b) => a.readiness_score - b.readiness_score)
    .slice(0, MAX_ROWS);

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
      <div className="flex items-center justify-between mb-1">
        <h4 className="text-sm font-semibold text-gray-700">Most At-Risk Shifts</h4>
        <Link to="/readiness" className="text-xs font-medium text-blue-600 hover:text-blue-800 flex items-center gap-1">
          View all {data.length} shifts <ArrowRight className="w-3 h-3" />
        </Link>
      </div>
      <p className="text-xs text-gray-400 mb-3">Lowest readiness office • time • direction combinations right now</p>

      {worst.length === 0 ? (
        <div className="p-6 text-center text-sm text-gray-400">No shift data available</div>
      ) : (
        <div className="divide-y divide-gray-100">
          {worst.map((shift, i) => {
            const pct = toPct(shift.readiness_score) ?? 0;
            const colorClass = pct >= 85 ? 'text-green-600' : pct >= 75 ? 'text-yellow-600' : 'text-red-600';
            const barColor = pct >= 85 ? 'bg-green-500' : pct >= 75 ? 'bg-yellow-500' : 'bg-red-500';

            return (
              <div key={`${shift.office}-${shift.shift}-${shift.direction}-${i}`} className="flex items-center gap-4 py-3">
                <div className="w-5 text-xs font-semibold text-gray-400">{i + 1}</div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-900 truncate">{shift.office}</div>
                  <div className="text-xs text-gray-500">{shift.shift} • {shift.direction}</div>
                  <div className="mt-1.5 h-1.5 w-full bg-gray-100 rounded-full overflow-hidden">
                    <div className={`h-full ${barColor}`} style={{ width: `${Math.max(pct, 2)}%` }} />
                  </div>
                </div>
                <div className="text-right w-20 flex-shrink-0">
                  <div className={`font-bold ${colorClass}`}>{pct}%</div>
                  <div className="text-xs text-gray-500">
                    {shift.employees_at_risk > 0 ? `${shift.employees_at_risk} at risk` : 'On track'}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
