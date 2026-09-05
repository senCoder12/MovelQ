import React from 'react';
import { ActionOption, ActionType } from '../types';
import { CheckCircle2, AlertCircle } from 'lucide-react';
import clsx from 'clsx';

export default function DecisionPanel({ 
  options, 
  recommendedAction, 
  onTakeAction 
}: { 
  options: ActionOption[], 
  recommendedAction: ActionType | null,
  onTakeAction: (a: ActionType) => void 
}) {
  return (
    <div className="space-y-4">
      {options.map((opt) => {
        const isRecommended = opt.action_type === recommendedAction;
        return (
          <div 
            key={opt.action_type} 
            className={clsx(
              "border rounded-lg p-5 transition-all",
              isRecommended ? "border-blue-500 bg-blue-50 ring-1 ring-blue-500" : "border-gray-200 bg-white"
            )}
          >
            <div className="flex justify-between items-start mb-4">
              <div>
                <div className="flex items-center gap-2">
                  <h4 className="text-lg font-bold text-gray-900">{opt.action_type.replace(/_/g, ' ')}</h4>
                  {isRecommended && (
                    <span className="inline-flex items-center gap-1 bg-blue-100 text-blue-700 px-2.5 py-0.5 rounded-full text-xs font-semibold">
                      <CheckCircle2 className="w-3 h-3" /> Recommended
                    </span>
                  )}
                </div>
                <p className="text-sm text-gray-600 mt-1">{opt.description}</p>
              </div>
              <button 
                onClick={() => onTakeAction(opt.action_type)}
                className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700 transition-colors"
              >
                Take Action
              </button>
            </div>
            <div className="grid grid-cols-3 gap-4 text-sm mt-4 pt-4 border-t border-gray-100">
              <div>
                <span className="block text-gray-500 font-semibold mb-1">Expected Impact</span>
                <span className="text-gray-900">{opt.expected_impact}</span>
              </div>
              <div>
                <span className="block text-gray-500 font-semibold mb-1">Estimated Cost</span>
                <span className="text-gray-900">{opt.estimated_cost}</span>
              </div>
              <div>
                <span className="block text-gray-500 font-semibold mb-1">Confidence</span>
                <span className="text-gray-900">{opt.confidence}</span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
