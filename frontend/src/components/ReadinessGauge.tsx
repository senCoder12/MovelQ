import React from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';

interface ReadinessGaugeProps {
  score: number;
  baseline?: number | null;
  compact?: boolean;
}

export default function ReadinessGauge({ score, baseline, compact = false }: ReadinessGaugeProps) {
  // Normalize score and baseline to 0..100 percentage scale
  const normScore = score <= 1.0 ? Math.round(score * 1000) / 10 : Math.round(score * 10) / 10;
  const clampedScore = Math.max(0, Math.min(100, normScore));
  
  const normBaseline = baseline != null 
    ? (baseline <= 1.0 ? Math.round(baseline * 1000) / 10 : Math.round(baseline * 10) / 10)
    : null;

  const color = clampedScore >= 85 ? '#22c55e' : clampedScore >= 75 ? '#eab308' : '#ef4444';

  if (compact) {
    // Compact radial ring for cards
    const strokeWidth = 5;
    const radius = 24;
    const circumference = 2 * Math.PI * radius;
    const strokeDashoffset = circumference - (clampedScore / 100) * circumference;

    return (
      <div className="relative flex items-center justify-center w-16 h-16">
        <svg className="w-16 h-16 transform -rotate-90">
          <circle
            cx="32"
            cy="32"
            r={radius}
            stroke="#f1f5f9"
            strokeWidth={strokeWidth}
            fill="transparent"
          />
          <circle
            cx="32"
            cy="32"
            r={radius}
            stroke={color}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            fill="transparent"
            className="transition-all duration-700 ease-out"
          />
        </svg>
        <span className="absolute text-xs font-bold text-gray-800">
          {clampedScore}%
        </span>
      </div>
    );
  }

  const data = [
    { name: 'Ready', value: clampedScore },
    { name: 'Risk', value: Math.max(0, 100 - clampedScore) },
  ];

  return (
    <div className="flex flex-col items-center justify-center relative w-48 h-48">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="55%"
            startAngle={180}
            endAngle={0}
            innerRadius={58}
            outerRadius={78}
            paddingAngle={0}
            dataKey="value"
            stroke="none"
          >
            <Cell fill={color} />
            <Cell fill="#f1f5f9" />
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <div className="absolute flex flex-col items-center top-[42%] text-center">
        <span className="text-3xl font-bold text-gray-900">{clampedScore}%</span>
        {normBaseline != null && (
          <span className="text-xs text-gray-500 mt-0.5">vs {normBaseline}% avg</span>
        )}
      </div>
    </div>
  );
}
