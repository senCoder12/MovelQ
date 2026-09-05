import React, { useState } from 'react';
import { useFetch } from '../../hooks/useFetch';
import { api } from '../../services/api';
import PriorityBadge from '../../components/PriorityBadge';
import StatusBadge from '../../components/StatusBadge';
import { Link } from 'react-router-dom';
import {
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  ShieldCheck,
  Clock,
  Users,
  X,
  ChevronRight,
} from 'lucide-react';

export default function DecisionsPage() {
  const { data: decisionItems, loading, error, refetch } = useFetch(() => api.getDecisions());
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<Record<string, string>>({});
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const handleExecuteAction = async (situationId: string, actionType: string) => {
    setActionInProgress(`${situationId}-${actionType}`);
    try {
      await api.takeAction(situationId, actionType);
      setActionSuccess(prev => ({
        ...prev,
        [situationId]: `Action "${actionType.replace(/_/g, ' ')}" recorded. Monitoring outcome.`
      }));
      refetch();
    } catch (e: any) {
      alert(`Failed to record action: ${e.message}`);
    } finally {
      setActionInProgress(null);
    }
  };

  if (loading) return <div className="p-8 text-gray-500">Loading decision matrix...</div>;
  if (error) return <div className="p-8 text-red-500">Error loading decisions.</div>;

  const selected = decisionItems?.find((d: any) => d.situation.situation_id === selectedId);

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      <div>
        <h2 className="text-3xl font-bold text-gray-900">Decision Intelligence Matrix</h2>
        <p className="text-gray-500 mt-1">
          Evaluate counterfactual actions, cost-benefit trade-offs, and operational interventions
        </p>
      </div>

      {decisionItems && decisionItems.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {decisionItems.map(({ situation, decision }: any) => {
            const hasSuccess = actionSuccess[situation.situation_id];
            return (
              <button
                key={situation.situation_id}
                onClick={() => setSelectedId(situation.situation_id)}
                className="text-left bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md hover:border-blue-300 transition-all p-4 flex flex-col gap-3"
              >
                <div className="flex items-center justify-between gap-2">
                  <PriorityBadge priority={situation.priority} />
                  <StatusBadge status={situation.status} />
                </div>

                <div>
                  <div className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-0.5">
                    {situation.business_unit} • {situation.office || 'Fleet-wide'}
                  </div>
                  <h3 className="text-sm font-bold text-gray-900 line-clamp-2">{situation.title}</h3>
                </div>

                <div className="flex flex-wrap gap-3 text-xs text-gray-600">
                  <div className="flex items-center gap-1">
                    <Users className="w-3.5 h-3.5 text-gray-400" />
                    <span>{situation.impact.affected_employees} affected</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5 text-gray-400" />
                    <span>{situation.impact.delay_p95 || situation.impact.delay_minutes_total || 0}m P95</span>
                  </div>
                </div>

                {decision?.recommended_action && (
                  <div className="flex items-center gap-1.5 bg-blue-50 border border-blue-100 rounded-lg px-2.5 py-1.5 mt-auto">
                    <ShieldCheck className="w-3.5 h-3.5 text-blue-600 flex-shrink-0" />
                    <span className="text-[10px] font-bold uppercase tracking-wide text-blue-700">AI Recommended</span>
                    <span className="text-xs font-semibold text-blue-900 truncate">
                      {decision.recommended_action.replace(/_/g, ' ')}
                    </span>
                  </div>
                )}

                {hasSuccess && (
                  <div className="flex items-center gap-1.5 text-xs text-green-700 font-medium">
                    <CheckCircle2 className="w-3.5 h-3.5 text-green-600" />
                    Action recorded
                  </div>
                )}

                <div className="flex items-center justify-end text-xs font-medium text-blue-600">
                  View details <ChevronRight className="w-3.5 h-3.5" />
                </div>
              </button>
            );
          })}
        </div>
      ) : (
        <div className="p-12 text-center text-gray-500 bg-white rounded-xl border border-gray-200">
          <CheckCircle2 className="w-12 h-12 text-green-500 mx-auto mb-3" />
          <h3 className="text-lg font-bold text-gray-900 mb-1">No Open Decisions Required</h3>
          <p className="text-sm text-gray-500 max-w-md mx-auto">
            All active shifts and routes are performing within expected baseline thresholds.
          </p>
        </div>
      )}

      {selected && (
        <DecisionDetailModal
          situation={selected.situation}
          decision={selected.decision}
          actionInProgress={actionInProgress}
          successMessage={actionSuccess[selected.situation.situation_id]}
          onExecute={handleExecuteAction}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  );
}

function DecisionDetailModal({
  situation,
  decision,
  actionInProgress,
  successMessage,
  onExecute,
  onClose,
}: {
  situation: any;
  decision: any;
  actionInProgress: string | null;
  successMessage?: string;
  onExecute: (situationId: string, actionType: string) => void;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-start justify-center z-50 p-4 overflow-y-auto">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-4xl my-8">
        <div className="flex items-start justify-between gap-4 px-6 py-4 border-b border-gray-100">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <PriorityBadge priority={situation.priority} />
              <StatusBadge status={situation.status} />
              <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                {situation.business_unit} • {situation.office || 'Fleet-wide'} • {situation.shift || ''}
              </span>
            </div>
            <h3 className="text-xl font-bold text-gray-900">{situation.title}</h3>
            <p className="text-gray-600 text-sm mt-1">{situation.description}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 flex-shrink-0">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Impact Summary Pill Grid */}
        <div className="flex flex-wrap gap-4 px-6 py-4 border-b border-gray-100 text-xs text-gray-600">
          <div className="flex items-center gap-1">
            <Users className="w-4 h-4 text-gray-400" />
            <span>Affected: <strong>{situation.impact.affected_employees} employees</strong></span>
          </div>
          <div className="flex items-center gap-1">
            <Clock className="w-4 h-4 text-gray-400" />
            <span>Delay: <strong>{situation.impact.delay_p95 || situation.impact.delay_minutes_total || 0}m P95</strong></span>
          </div>
          <div className="flex items-center gap-1">
            <AlertTriangle className="w-4 h-4 text-gray-400" />
            <span>Readiness Delta: <strong className="text-red-600">{situation.impact.readiness_delta_pp || 0}%</strong></span>
          </div>
          <Link
            to={`/situations/${situation.situation_id}`}
            className="ml-auto text-sm font-medium text-blue-600 hover:text-blue-800 flex items-center gap-1"
          >
            View Situation Details <ArrowRight className="w-4 h-4" />
          </Link>
        </div>

        {/* AI Recommendation Banner */}
        {decision?.recommended_action && (
          <div className="bg-blue-50/80 px-6 py-4 border-b border-blue-100 flex items-start gap-3">
            <ShieldCheck className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold uppercase tracking-wider text-blue-700 bg-blue-100 px-2 py-0.5 rounded">
                  AI Recommended
                </span>
                <span className="font-bold text-blue-900">
                  {decision.recommended_action.replace(/_/g, ' ')}
                </span>
              </div>
              <p className="text-sm text-blue-800 mt-1">{decision.recommendation_reasoning}</p>
            </div>
          </div>
        )}

        {successMessage && (
          <div className="bg-green-50 px-6 py-3 border-b border-green-200 flex items-center gap-2 text-sm text-green-800 font-medium">
            <CheckCircle2 className="w-4 h-4 text-green-600" />
            {successMessage}
          </div>
        )}

        {/* Candidate Options */}
        <div className="p-6 space-y-3">
          <h4 className="text-sm font-bold text-gray-900 uppercase tracking-wider mb-1">
            Candidate Options Comparison
          </h4>

          {decision?.options?.map((opt: any, idx: number) => {
            const isRecommended = opt.action_type === decision.recommended_action;
            const loadingBtn = actionInProgress === `${situation.situation_id}-${opt.action_type}`;

            return (
              <div
                key={idx}
                className={`rounded-lg border p-4 ${isRecommended ? 'border-blue-200 bg-blue-50/30' : 'border-gray-200'}`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-gray-900">{opt.action_type.replace(/_/g, ' ')}</span>
                      {isRecommended && (
                        <span className="text-[10px] bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded font-bold">
                          BEST
                        </span>
                      )}
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-gray-100 text-gray-800">
                        {opt.confidence} confidence
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5">{opt.description}</p>
                  </div>
                  <button
                    onClick={() => onExecute(situation.situation_id, opt.action_type)}
                    disabled={loadingBtn || situation.status === 'ACTIONED'}
                    className={`flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                      isRecommended
                        ? 'bg-blue-600 text-white hover:bg-blue-700 shadow-sm'
                        : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
                    } disabled:opacity-50 disabled:cursor-not-allowed`}
                  >
                    {loadingBtn ? 'Executing...' : situation.status === 'ACTIONED' ? 'Actioned' : 'Execute Action'}
                  </button>
                </div>

                <div className="grid grid-cols-2 gap-3 mt-3 pt-3 border-t border-gray-100 text-xs">
                  <div>
                    <div className="text-gray-400 font-semibold uppercase tracking-wide text-[10px] mb-0.5">Expected Impact</div>
                    <div className="text-emerald-700 font-semibold">{opt.expected_impact}</div>
                  </div>
                  <div>
                    <div className="text-gray-400 font-semibold uppercase tracking-wide text-[10px] mb-0.5">Estimated Cost</div>
                    <div className="text-gray-700 font-mono">{opt.estimated_cost}</div>
                  </div>
                </div>

                {(opt.supporting_evidence?.length > 0 || opt.assumptions?.length > 0) && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3 pt-3 border-t border-gray-100 text-xs">
                    {opt.supporting_evidence?.length > 0 && (
                      <div>
                        <div className="text-gray-400 font-semibold uppercase tracking-wide text-[10px] mb-1">
                          Supporting Evidence {opt.evidence_type ? `(${opt.evidence_type.replace(/_/g, ' ')})` : ''}
                        </div>
                        <ul className="list-disc list-inside text-gray-600 space-y-0.5">
                          {opt.supporting_evidence.map((e: string, i: number) => (
                            <li key={i}>{e}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {opt.assumptions?.length > 0 && (
                      <div>
                        <div className="text-gray-400 font-semibold uppercase tracking-wide text-[10px] mb-1">Assumptions</div>
                        <ul className="list-disc list-inside text-gray-600 space-y-0.5">
                          {opt.assumptions.map((a: string, i: number) => (
                            <li key={i}>{a}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
