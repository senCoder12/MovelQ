import React from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell, ReferenceLine, LabelList } from 'recharts';
import { ShiftReadiness } from '../types';

const WARNING_THRESHOLD = 85;
const CRITICAL_THRESHOLD = 75;

function aggregateByBusinessUnit(data: ShiftReadiness[]) {
  const groups = new Map<string, { expected: number; ready: number; baselineSum: number; baselineWeight: number; atRisk: number }>();

  for (const row of data) {
    const g = groups.get(row.business_unit) ?? { expected: 0, ready: 0, baselineSum: 0, baselineWeight: 0, atRisk: 0 };
    g.expected += row.employees_expected;
    g.ready += row.employees_ready_on_time;
    g.atRisk += row.employees_at_risk;
    if (row.historical_baseline != null) {
      g.baselineSum += row.historical_baseline * row.employees_expected;
      g.baselineWeight += row.employees_expected;
    }
    groups.set(row.business_unit, g);
  }

  return [...groups.entries()]
    .map(([name, g]) => {
      const readinessRaw = g.expected > 0 ? g.ready / g.expected : 0;
      const baselineRaw = g.baselineWeight > 0 ? g.baselineSum / g.baselineWeight : null;
      return {
        name,
        readiness: Math.round(readinessRaw * 1000) / 10,
        baseline: baselineRaw != null ? Math.round(baselineRaw * 1000) / 10 : null,
        employees: g.expected,
        atRisk: g.atRisk,
      };
    })
    .sort((a, b) => a.readiness - b.readiness);
}

export default function ReadinessByBusinessUnitChart({ data }: { data: ShiftReadiness[] }) {
  const chartData = aggregateByBusinessUnit(data);

  return (
    <div className="h-80 w-full bg-white p-4 rounded-lg border border-gray-200 shadow-sm flex flex-col">
      <h4 className="text-sm font-semibold text-gray-700">Readiness by Business Unit</h4>
      <p className="text-xs text-gray-400 mb-2">
        Employee-weighted readiness vs. baseline, across {chartData.length} business units
      </p>
      {chartData.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-sm text-gray-400">No readiness data available</div>
      ) : (
        <>
          <div className="flex-1 min-h-0">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 16, right: 10, left: -10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} interval={0} />
                <YAxis
                  domain={[0, 100]}
                  tick={{ fontSize: 11 }}
                  tickFormatter={(v) => `${v}%`}
                  axisLine={false}
                  tickLine={false}
                  width={36}
                />
                <Tooltip
                  cursor={{ fill: '#f8fafc' }}
                  formatter={(value: number, name: string) => [value == null ? 'N/A' : `${value}%`, name]}
                  labelFormatter={(label, payload) =>
                    payload?.[0]?.payload ? `${label} • ${payload[0].payload.employees.toLocaleString()} employees` : label
                  }
                />
                <ReferenceLine
                  y={WARNING_THRESHOLD}
                  stroke="#22c55e"
                  strokeDasharray="4 4"
                  label={{ value: `Target ${WARNING_THRESHOLD}%`, position: 'insideTopRight', fill: '#16a34a', fontSize: 10 }}
                />
                <ReferenceLine
                  y={CRITICAL_THRESHOLD}
                  stroke="#ef4444"
                  strokeDasharray="4 4"
                  label={{ value: `Critical ${CRITICAL_THRESHOLD}%`, position: 'insideBottomRight', fill: '#dc2626', fontSize: 10 }}
                />
                <Bar dataKey="readiness" name="Readiness" radius={[4, 4, 0, 0]} maxBarSize={56}>
                  <LabelList dataKey="readiness" position="top" formatter={(v: number) => `${v}%`} fontSize={10} fill="#374151" />
                  {chartData.map((entry, i) => (
                    <Cell
                      key={i}
                      fill={entry.readiness >= WARNING_THRESHOLD ? '#22c55e' : entry.readiness >= CRITICAL_THRESHOLD ? '#eab308' : '#ef4444'}
                    />
                  ))}
                </Bar>
                <Bar dataKey="baseline" name="Baseline" fill="#cbd5e1" radius={[4, 4, 0, 0]} maxBarSize={56} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="flex flex-wrap items-center gap-3 mt-2 pt-2 border-t border-gray-100 text-[11px] text-gray-500">
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-500" /> Healthy (&ge;{WARNING_THRESHOLD}%)</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-yellow-500" /> Watch ({CRITICAL_THRESHOLD}-{WARNING_THRESHOLD}%)</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500" /> Critical (&lt;{CRITICAL_THRESHOLD}%)</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-slate-300" /> Baseline avg</span>
          </div>
        </>
      )}
    </div>
  );
}
