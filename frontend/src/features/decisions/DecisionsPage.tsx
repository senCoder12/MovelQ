import React, { useState } from 'react';
import { useFetch } from '../../hooks/useFetch';
import { api } from '../../services/api';
import PriorityBadge from '../../components/PriorityBadge';
import StatusBadge from '../../components/StatusBadge';
import { Link } from 'react-router-dom';
import { CheckCircle2, AlertTriangle, ArrowRight, ShieldCheck, DollarSign, Clock, Users } from 'lucide-react';

export default function DecisionsPage() {
  const { data: decisionItems, loading, error, refetch } = useFetch(() => api.getDecisions());
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<Record<string, string>>({});

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

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      <div>
        <h2 className="text-3xl font-bold text-gray-900">Decision Intelligence Matrix</h2>
        <p className="text-gray-500 mt-1">
          Evaluate counterfactual actions, cost-benefit trade-offs, and operational interventions
        </p>
      </div>

      <div className="space-y-6">
        {decisionItems && decisionItems.length > 0 ? (
          decisionItems.map(({ situation, decision }: any) => {
            const hasSuccess = actionSuccess[situation.situation_id];
            
            return (
              <div 
                key={situation.situation_id} 
                className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden"
              >
                {/* Situation Header */}
                <div className="p-6 border-b border-gray-100 bg-gray-50/50">
                  <div className="flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                      <PriorityBadge priority={situation.priority} />
                      <StatusBadge status={situation.status} />
                      <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                        {situation.business_unit} • {situation.office || 'Fleet-wide'} • {situation.shift || ''}
                      </span>
                    </div>
                    <Link
                      to={`/situations/${situation.situation_id}`}
                      className="text-sm font-medium text-blue-600 hover:text-blue-800 flex items-center gap-1"
                    >
                      View Situation Details <ArrowRight className="w-4 h-4" />
                    </Link>
                  </div>

                  <h3 className="text-xl font-bold text-gray-900 mt-3">{situation.title}</h3>
                  <p className="text-gray-600 text-sm mt-1">{situation.description}</p>

                  {/* Impact Summary Pill Grid */}
                  <div className="flex flex-wrap gap-4 mt-4 pt-3 border-t border-gray-200/60 text-xs text-gray-600">
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
                  </div>
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
                      <p className="text-sm text-blue-800 mt-1">
                        {decision.recommendation_reasoning}
                      </p>
                    </div>
                  </div>
                )}

                {/* Action Feedback Banner */}
                {hasSuccess && (
                  <div className="bg-green-50 px-6 py-3 border-b border-green-200 flex items-center gap-2 text-sm text-green-800 font-medium">
                    <CheckCircle2 className="w-4 h-4 text-green-600" />
                    {hasSuccess}
                  </div>
                )}

                {/* Candidate Options Table */}
                <div className="p-6">
                  <h4 className="text-sm font-bold text-gray-900 uppercase tracking-wider mb-4">
                    Candidate Options Comparison
                  </h4>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm">
                      <thead className="bg-gray-50 text-gray-500 uppercase text-xs">
                        <tr>
                          <th className="py-3 px-4 rounded-l-lg font-semibold">Action Option</th>
                          <th className="py-3 px-4 font-semibold">Expected Impact</th>
                          <th className="py-3 px-4 font-semibold">Estimated Cost</th>
                          <th className="py-3 px-4 font-semibold">Confidence</th>
                          <th className="py-3 px-4 rounded-r-lg font-semibold text-right">Intervention</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {decision?.options?.map((opt: any, idx: number) => {
                          const isRecommended = opt.action_type === decision.recommended_action;
                          const loadingBtn = actionInProgress === `${situation.situation_id}-${opt.action_type}`;

                          return (
                            <tr key={idx} className={isRecommended ? 'bg-blue-50/30' : 'hover:bg-gray-50'}>
                              <td className="py-3.5 px-4 font-medium text-gray-900">
                                <div className="flex items-center gap-2">
                                  <span>{opt.action_type.replace(/_/g, ' ')}</span>
                                  {isRecommended && (
                                    <span className="text-[10px] bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded font-bold">
                                      BEST
                                    </span>
                                  )}
                                </div>
                                <div className="text-xs text-gray-500 font-normal mt-0.5">
                                  {opt.description}
                                </div>
                              </td>
                              <td className="py-3.5 px-4 text-gray-700">
                                <span className="font-semibold text-emerald-700">{opt.expected_impact}</span>
                              </td>
                              <td className="py-3.5 px-4 text-gray-600">
                                <span className="font-mono">{opt.estimated_cost}</span>
                              </td>
                              <td className="py-3.5 px-4">
                                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">
                                  {opt.confidence}
                                </span>
                              </td>
                              <td className="py-3.5 px-4 text-right">
                                <button
                                  onClick={() => handleExecuteAction(situation.situation_id, opt.action_type)}
                                  disabled={loadingBtn || situation.status === 'ACTIONED'}
                                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                                    isRecommended
                                      ? 'bg-blue-600 text-white hover:bg-blue-700 shadow-sm'
                                      : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
                                  } disabled:opacity-50 disabled:cursor-not-allowed`}
                                >
                                  {loadingBtn ? 'Executing...' : situation.status === 'ACTIONED' ? 'Actioned' : 'Execute Action'}
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            );
          })
        ) : (
          <div className="p-12 text-center text-gray-500 bg-white rounded-xl border border-gray-200">
            <CheckCircle2 className="w-12 h-12 text-green-500 mx-auto mb-3" />
            <h3 className="text-lg font-bold text-gray-900 mb-1">No Open Decisions Required</h3>
            <p className="text-sm text-gray-500 max-w-md mx-auto">
              All active shifts and routes are performing within expected baseline thresholds.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
