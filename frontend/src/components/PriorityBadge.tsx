import React from 'react';
import clsx from 'clsx';
import { SituationPriority } from '../types';

export default function PriorityBadge({ priority }: { priority: SituationPriority }) {
  const colors = {
    CRITICAL: 'bg-red-100 text-red-800 border-red-200',
    HIGH: 'bg-orange-100 text-orange-800 border-orange-200',
    MEDIUM: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    LOW: 'bg-blue-100 text-blue-800 border-blue-200',
    INFO: 'bg-gray-100 text-gray-800 border-gray-200',
  };
  return (
    <span className={clsx('px-2.5 py-0.5 rounded-full text-xs font-medium border', colors[priority] || 'bg-gray-100 text-gray-800 border-gray-200')}>
      {priority}
    </span>
  );
}
