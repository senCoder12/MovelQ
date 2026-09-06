import React, { useState } from 'react';
import { X, Siren, CheckCircle2, Info } from 'lucide-react';
import { api } from '../services/api';

type Priority = 'HIGH' | 'LOW';

interface Result {
  priority: string;
  situation_created: boolean;
  message: string;
  trip_id: number;
}

export default function SimulateAlertModal({ onClose }: { onClose: () => void }) {
  const [alertName, setAlertName] = useState('');
  const [priority, setPriority] = useState<Priority>('HIGH');
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!alertName.trim()) return;
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.simulateAlert(alertName.trim(), priority);
      setResult(res);
    } catch (e) {
      setError('Failed to submit alert. Is the backend running?');
    } finally {
      setSubmitting(false);
    }
  };

  const reset = () => {
    setAlertName('');
    setResult(null);
    setError(null);
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <Siren className="w-5 h-5 text-red-500" />
            <h3 className="text-lg font-bold text-gray-900">Simulate Alert</h3>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="px-6 py-5 space-y-5">
          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              Alert Name
            </label>
            <input
              type="text"
              value={alertName}
              onChange={e => setAlertName(e.target.value)}
              placeholder="e.g. Vehicle Stoppage, Engine Overheat..."
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={submitting}
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              Priority
            </label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setPriority('HIGH')}
                disabled={submitting}
                className={`px-4 py-3 rounded-md border text-sm font-semibold transition-colors ${
                  priority === 'HIGH'
                    ? 'bg-red-50 border-red-400 text-red-700 ring-1 ring-red-400'
                    : 'bg-white border-gray-300 text-gray-600 hover:bg-gray-50'
                }`}
              >
                High Priority
                <div className="text-xs font-normal mt-1 opacity-80">Reaches the dashboard</div>
              </button>
              <button
                type="button"
                onClick={() => setPriority('LOW')}
                disabled={submitting}
                className={`px-4 py-3 rounded-md border text-sm font-semibold transition-colors ${
                  priority === 'LOW'
                    ? 'bg-gray-100 border-gray-400 text-gray-700 ring-1 ring-gray-400'
                    : 'bg-white border-gray-300 text-gray-600 hover:bg-gray-50'
                }`}
              >
                Low Priority
                <div className="text-xs font-normal mt-1 opacity-80">Logged only, filtered out</div>
              </button>
            </div>
          </div>

          {error && (
            <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">
              {error}
            </div>
          )}

          {result && (
            <div
              className={`flex gap-2 text-sm rounded-md px-3 py-3 border ${
                result.priority === 'LOW'
                  ? 'bg-gray-50 border-gray-200 text-gray-700'
                  : result.situation_created
                  ? 'bg-green-50 border-green-200 text-green-800'
                  : 'bg-yellow-50 border-yellow-200 text-yellow-800'
              }`}
            >
              {result.priority === 'LOW' ? (
                <Info className="w-4 h-4 flex-shrink-0 mt-0.5" />
              ) : (
                <CheckCircle2 className="w-4 h-4 flex-shrink-0 mt-0.5" />
              )}
              <div>
                <div>{result.message}</div>
                <div className="text-xs opacity-70 mt-1">Trip ID {result.trip_id}</div>
              </div>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-100">
          {result ? (
            <>
              <button
                onClick={reset}
                className="px-4 py-2 text-sm font-medium rounded-md border border-gray-300 text-gray-700 hover:bg-gray-50"
              >
                Simulate Another
              </button>
              <button
                onClick={onClose}
                className="px-4 py-2 text-sm font-medium rounded-md bg-blue-600 text-white hover:bg-blue-700"
              >
                Done
              </button>
            </>
          ) : (
            <>
              <button
                onClick={onClose}
                disabled={submitting}
                className="px-4 py-2 text-sm font-medium rounded-md border border-gray-300 text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={submit}
                disabled={submitting || !alertName.trim()}
                className="px-4 py-2 text-sm font-medium rounded-md bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submitting ? 'Submitting...' : 'Trigger Alert'}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
