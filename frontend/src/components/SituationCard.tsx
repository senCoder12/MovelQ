import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, Clock, CheckCircle2 } from 'lucide-react';
import { Situation } from '../types';
import { api } from '../services/api';
import PriorityBadge from './PriorityBadge';
import StatusBadge from './StatusBadge';

const RESOLVABLE_STATUSES = new Set(['ACTION_RECOMMENDED', 'ACTION_PENDING', 'ACTIONED', 'VERIFYING']);

export default function SituationCard({ situation, onResolved }: { situation: Situation; onResolved?: () => void }) {
  const navigate = useNavigate();
  const [resolving, setResolving] = useState(false);
  const canResolve = RESOLVABLE_STATUSES.has(situation.status);

  const handleResolve = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (resolving) return;
    setResolving(true);
    try {
      await api.resolveSituation(situation.situation_id);
      onResolved?.();
    } catch (err) {
      console.error('Failed to resolve situation', err);
    } finally {
      setResolving(false);
    }
  };

  return (
    <div
      onClick={() => navigate(`/situations/${situation.situation_id}`)}
      className="bg-white p-5 rounded-lg border border-gray-200 shadow-sm hover:shadow-md cursor-pointer transition-shadow"
    >
      <div className="flex justify-between items-start mb-3">
        <div className="flex items-center gap-2">
          <PriorityBadge priority={situation.priority} />
          <span className="text-sm text-gray-500 flex items-center gap-1">
            <Clock className="w-4 h-4" />
            {new Date(situation.first_seen).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
          </span>
        </div>
        <StatusBadge status={situation.status} />
      </div>
      <h3 className="text-lg font-semibold text-gray-900 mb-2 flex items-center gap-2">
        <AlertTriangle className="w-5 h-5 text-gray-400" />
        {situation.title}
      </h3>
      <p className="text-sm text-gray-600 mb-4 line-clamp-2">{situation.description}</p>

      <div className="grid grid-cols-2 gap-4 pt-4 border-t border-gray-100">
        <div>
          <div className="text-xs text-gray-500 uppercase font-semibold">Impact</div>
          <div className="text-sm font-medium text-gray-900">
            {situation.impact.affected_employees} Employees at Risk
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-500 uppercase font-semibold">Trips Affected</div>
          <div className="text-sm font-medium text-gray-900">
            {situation.impact.affected_trips} Trips
          </div>
        </div>
      </div>

      {canResolve && (
        <button
          onClick={handleResolve}
          disabled={resolving}
          className="mt-4 w-full flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium rounded-md bg-green-50 text-green-700 border border-green-200 hover:bg-green-100 transition-colors disabled:opacity-50"
        >
          <CheckCircle2 className="w-4 h-4" />
          {resolving ? 'Resolving...' : 'Mark Resolved'}
        </button>
      )}
    </div>
  );
}
