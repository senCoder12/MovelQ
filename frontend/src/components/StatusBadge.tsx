import React from 'react';
import clsx from 'clsx';
import { SituationStatus } from '../types';

export default function StatusBadge({ status }: { status: SituationStatus }) {
  const colors = {
    DETECTED: 'bg-yellow-100 text-yellow-800',
    INVESTIGATING: 'bg-blue-100 text-blue-800',
    ACTION_RECOMMENDED: 'bg-purple-100 text-purple-800',
    ACTION_PENDING: 'bg-orange-100 text-orange-800',
    ACTIONED: 'bg-indigo-100 text-indigo-800',
    VERIFYING: 'bg-teal-100 text-teal-800',
    RESOLVED: 'bg-green-100 text-green-800',
    DISMISSED: 'bg-gray-100 text-gray-800',
  };
  return (
    <span className={clsx('px-2.5 py-0.5 rounded-full text-xs font-medium', colors[status] || 'bg-gray-100 text-gray-800')}>
      {status.replace('_', ' ')}
    </span>
  );
}
