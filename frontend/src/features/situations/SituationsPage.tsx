import React, { useState } from 'react';
import { useFetch } from '../../hooks/useFetch';
import { api } from '../../services/api';
import SituationCard from '../../components/SituationCard';

export default function SituationsPage() {
  const { data: situations, loading, error } = useFetch(() => api.getSituations(), [], 5000);
  const [filter, setFilter] = useState('ALL');

  if (loading) return <div className="p-8">Loading situations...</div>;
  if (error) return <div className="p-8 text-red-500">Error loading situations.</div>;
  
  const filtered = situations?.filter(s => filter === 'ALL' || s.status === filter) || [];

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-3xl font-bold text-gray-900">Situations</h2>
          <p className="text-gray-500 mt-1">Monitor and resolve active operational risks</p>
        </div>
        <div className="flex gap-2">
          {['ALL', 'ACTION_RECOMMENDED', 'INVESTIGATING', 'RESOLVED'].map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                filter === f ? 'bg-blue-600 text-white' : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
              }`}
            >
              {f.replace('_', ' ')}
            </button>
          ))}
        </div>
      </div>
      
      <div className="grid grid-cols-2 gap-6">
        {filtered.map(sit => (
          <SituationCard key={sit.situation_id} situation={sit} />
        ))}
        {filtered.length === 0 && (
          <div className="col-span-2 p-12 text-center text-gray-500 bg-white rounded-lg border border-gray-200">
            No situations found for this filter.
          </div>
        )}
      </div>
    </div>
  );
}
