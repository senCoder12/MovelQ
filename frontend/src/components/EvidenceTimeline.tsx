import React from 'react';
import { Clock } from 'lucide-react';
import { AlertEpisode } from '../types';

export default function EvidenceTimeline({ episodes }: { episodes: AlertEpisode[] }) {
  if (!episodes || episodes.length === 0) return <div className="text-gray-500 text-sm">No evidence timeline available.</div>;
  
  return (
    <div className="space-y-4">
      {episodes.map((ep, i) => (
        <div key={ep.episode_id || i} className="flex gap-4 relative">
          {i !== episodes.length - 1 && <div className="absolute left-[11px] top-6 bottom-[-16px] w-0.5 bg-gray-200"></div>}
          <div className="flex-none bg-blue-100 p-1 rounded-full text-blue-600 h-6 w-6 flex items-center justify-center mt-0.5 z-10">
            <Clock className="w-3 h-3" />
          </div>
          <div className="flex-1 bg-white border border-gray-200 rounded p-3">
            <div className="text-xs font-semibold text-gray-500 mb-1">
              {new Date(ep.first_seen).toLocaleTimeString()} - {ep.event_type}
            </div>
            <div className="text-sm text-gray-900">
              Trip {ep.trip_id} • Source: {ep.source || 'Unknown'} • Occurrences: {ep.occurrence_count}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
