import React from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from 'recharts';

export default function HistoricalComparison({ data }: { data: any[] }) {
  return (
    <div className="h-64 w-full bg-white p-4 rounded-lg border border-gray-200">
      <h4 className="text-sm font-semibold text-gray-700 mb-4">Current vs Historical Baseline</h4>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="name" axisLine={false} tickLine={false} />
          <YAxis axisLine={false} tickLine={false} />
          <Tooltip cursor={{fill: '#f8fafc'}} />
          <Legend />
          <Bar dataKey="current" fill="#3b82f6" name="Current" radius={[4, 4, 0, 0]} />
          <Bar dataKey="historical" fill="#cbd5e1" name="Historical P90" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
