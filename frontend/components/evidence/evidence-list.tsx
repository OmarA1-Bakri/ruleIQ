'use client';

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

interface Evidence {
  id: string;
  name: string;
  type: string;
  uploadDate: string;
  status: 'pending' | 'approved' | 'rejected';
}

interface EvidenceListProps {
  evidence?: Evidence[];
  onEvidenceClick?: (evidenceId: string) => void;
  onStatusChange?: (evidenceId: string, status: string) => void;
}

export function EvidenceList({
  evidence = [],
  onEvidenceClick,
  onStatusChange: _onStatusChange,
}: EvidenceListProps) {
  const defaultEvidence: Evidence[] = [
    {
      id: '1',
      name: 'Privacy Policy.pdf',
      type: 'document',
      uploadDate: '2024-01-15',
      status: 'approved',
    },
    {
      id: '2',
      name: 'Data Processing Agreement.docx',
      type: 'document',
      uploadDate: '2024-01-14',
      status: 'pending',
    },
  ];

  const displayEvidence = evidence.length > 0 ? evidence : defaultEvidence;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Evidence List</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {displayEvidence.map((item) => (
            <div
              key={item.id}
              className="flex items-center justify-between rounded border p-3"
              role="listitem"
            >
              <div>
                <div className="font-medium">{item.name}</div>
                <div className="text-sm text-gray-500">{item.uploadDate}</div>
              </div>
              <div className="flex items-center gap-2">
                <span
                  className={`rounded px-2 py-1 text-xs ${
                    item.status === 'approved'
                      ? 'bg-green-100 text-green-800'
                      : item.status === 'pending'
                        ? 'bg-yellow-100 text-yellow-800'
                        : 'bg-red-100 text-red-800'
                  }`}
                >
                  {item.status}
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => onEvidenceClick?.(item.id)}
                  tabIndex={0}
                >
                  View
                </Button>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
