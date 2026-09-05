import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { api } from '../../services/api';
import PriorityBadge from '../../components/PriorityBadge';
import StatusBadge from '../../components/StatusBadge';
import DecisionPanel from '../../components/DecisionPanel';
import EvidenceTimeline from '../../components/EvidenceTimeline';
import { AlertTriangle, TrendingDown, Users, Clock } from 'lucide-react';

export default function SituationDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  
  const { data: sit, loading: sLoading } = useFetch(() => api.getSituation(id!), [id]);
  const { data: decisions, loading: dLoading } = useFetch(() => api.getSituationDecisions(id!), [id]);
  
  if (sLoading || dLoading) return <div className="p-8">Loading details...</div>;
  if (!sit) return <div className="p-8 text-red-500">Situation not found.</div>;

  const decision = decisions && decisions.length > 0 ? decisions[0] : null;

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <button onClick={() => navigate(-1)} className="text-sm text-blue-600 hover:underline mb-4 block">
        &larr; Back to Situations
      </button>

      <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
        <div className="flex items-center gap-3 mb-4">
          <PriorityBadge priority={sit.priority} />
          <StatusBadge status={sit.status} />
          <span className="text-sm text-gray-500 ml-auto">First seen: {new Date(sit.first_seen).toLocaleString()}</span>
        </div>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">{sit.title}</h1>
        <p className="text-gray-600 text-lg mb-6">{sit.description}</p>
        
        <div className="grid grid-cols-4 gap-4 py-4 border-y border-gray-100">
          <div>
            <div className="text-sm text-gray-500 font-medium mb-1 flex items-center gap-1"><Users className="w-4 h-4"/> Affected Employees</div>
            <div className="text-2xl font-bold text-gray-900">{sit.impact.affected_employees}</div>
          </div>
          <div>
            <div className="text-sm text-gray-500 font-medium mb-1 flex items-center gap-1"><TrendingDown className="w-4 h-4"/> Readiness Delta</div>
            <div className="text-2xl font-bold text-red-600">{sit.impact.readiness_delta_pp}%</div>
          </div>
          <div>
            <div className="text-sm text-gray-500 font-medium mb-1 flex items-center gap-1"><Clock className="w-4 h-4"/> Delay Impact (P95)</div>
            <div className="text-2xl font-bold text-orange-600">{sit.impact.delay_p95 || 0} min</div>
          </div>
          <div>
            <div className="text-sm text-gray-500 font-medium mb-1 flex items-center gap-1"><AlertTriangle className="w-4 h-4"/> AI Confidence</div>
            <div className="text-2xl font-bold text-blue-600">{Math.round(sit.confidence * 100)}%</div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2 space-y-6">
          {decision && (
            <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
              <h3 className="text-xl font-bold text-gray-900 mb-4">Recommended Decisions</h3>
              <p className="text-sm text-gray-600 mb-6 bg-blue-50 p-3 rounded-md border border-blue-100">
                <strong>Reasoning:</strong> {decision.recommendation_reasoning}
              </p>
              <DecisionPanel 
                options={decision.options} 
                recommendedAction={decision.recommended_action}
                onTakeAction={(action) => {
                  api.takeAction(sit.situation_id, action)
                    .then(() => alert(`Action ${action} initiated.`))
                    .catch(e => alert(`Error: ${e.message}`));
                }}
              />
            </div>
          )}
        </div>
        <div className="space-y-6">
          <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
            <h3 className="text-lg font-bold text-gray-900 mb-4">Timeline Evidence</h3>
            <EvidenceTimeline episodes={[]} />
          </div>
        </div>
      </div>
    </div>
  );
}
