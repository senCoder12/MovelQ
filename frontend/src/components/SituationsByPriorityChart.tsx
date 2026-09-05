import React from 'react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { Situation, SituationPriority } from '../types';

const PRIORITY_ORDER: SituationPriority[] = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'];
const PRIORITY_COLORS: Record<SituationPriority, string> = {
  CRITICAL: '#ef4444',
  HIGH: '#f97316',
  MEDIUM: '#eab308',
  LOW: '#3b82f6',
  INFO: '#94a3b8',
};

interface Props {
  situations: Situation[];
  selected?: SituationPriority | null;
  onSelect?: (priority: SituationPriority | null) => void;
}

export default function SituationsByPriorityChart({ situations, selected, onSelect }: Props) {
  const counts = PRIORITY_ORDER.map(priority => ({
    name: priority,
    value: situations.filter(s => s.priority === priority).length,
  })).filter(c => c.value > 0);

  const total = situations.length;

  return (
    <div className="h-80 w-full bg-white p-4 rounded-lg border border-gray-200 shadow-sm flex flex-col">
      <h4 className="text-sm font-semibold text-gray-700">Situations by Priority</h4>
      <p className="text-xs text-gray-400 mb-2">Active situations grouped by urgency — click a slice to filter below</p>
      {counts.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-sm text-gray-400">No active situations</div>
      ) : (
        <div className="flex-1 min-h-0 relative">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={counts}
                cx="50%"
                cy="48%"
                innerRadius={48}
                outerRadius={72}
                paddingAngle={2}
                dataKey="value"
                stroke="none"
                onClick={(entry) => onSelect?.(selected === entry.name ? null : entry.name)}
                className="cursor-pointer"
              >
                {counts.map((entry) => (
                  <Cell
                    key={entry.name}
                    fill={PRIORITY_COLORS[entry.name as SituationPriority]}
                    opacity={selected && selected !== entry.name ? 0.35 : 1}
                  />
                ))}
              </Pie>
              <Tooltip formatter={(value: number, name: string) => [`${value} ${value === 1 ? 'situation' : 'situations'}`, name]} />
              <Legend
                iconSize={8}
                wrapperStyle={{ fontSize: 11, cursor: 'pointer' }}
                formatter={(value: string, entry: any) => `${value} (${entry.payload.value})`}
                onClick={(entry: any) => onSelect?.(selected === entry.value ? null : entry.value)}
              />
            </PieChart>
          </ResponsiveContainer>
          <div
            className="absolute inset-x-0 top-0 flex flex-col items-center justify-center pointer-events-none"
            style={{ height: '78%' }}
          >
            <span className="text-2xl font-bold text-gray-900">{total}</span>
            <span className="text-[10px] text-gray-500 uppercase tracking-wide">
              {total === 1 ? 'Active Situation' : 'Active Situations'}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
