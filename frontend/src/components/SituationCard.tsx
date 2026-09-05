import React from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, Clock } from 'lucide-react';
import { Situation } from '../types';
import PriorityBadge from './PriorityBadge';
import StatusBadge from './StatusBadge';

export default function SituationCard({ situation }: { situation: Situation }) {
  const navigate = useNavigate();
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
    </div>
  );
}
