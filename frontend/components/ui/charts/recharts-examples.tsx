'use client';

import React from 'react';
import {
  Line,
  AreaChart,
  Area,
  Bar,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ComposedChart,
} from 'recharts';

const data = [
  { month: 'Jan', compliance: 87, security: 92, performance: 78, users: 120 },
  { month: 'Feb', compliance: 89, security: 88, performance: 82, users: 145 },
  { month: 'Mar', compliance: 92, security: 95, performance: 88, users: 180 },
  { month: 'Apr', compliance: 94, security: 91, performance: 85, users: 210 },
  { month: 'May', compliance: 96, security: 93, performance: 90, users: 250 },
  { month: 'Jun', compliance: 98, security: 97, performance: 93, users: 320 },
];
const radarData = [
  { subject: 'Security', A: 120, B: 110, fullMark: 150 },
  { subject: 'Performance', A: 98, B: 130, fullMark: 150 },
  { subject: 'Compliance', A: 86, B: 130, fullMark: 150 },
  { subject: 'Reliability', A: 99, B: 100, fullMark: 150 },
  { subject: 'Scalability', A: 85, B: 90, fullMark: 150 },
  { subject: 'UX', A: 65, B: 85, fullMark: 150 },
];

const _pieData = [
  { name: 'Critical', value: 400, color: 'var(--purple-500)' },
  { name: 'High', value: 300, color: 'var(--purple-500)' },
  { name: 'Medium', value: 300, color: 'var(--purple-400)' },
  { name: 'Low', value: 200, color: 'var(--purple-50)' },
];

// Glowing Area Chart
export const GlowingAreaChart = () => {
  return (
    <div className="bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 rounded-2xl p-6 border border-purple-800/20">
      <h3 className="text-xl font-semibold text-white mb-4">Performance Trends</h3>
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={data}>
          <defs>
            <linearGradient id="colorCompliance" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="var(--purple-500)" stopOpacity={0.8}/>
              <stop offset="95%" stopColor="var(--purple-500)" stopOpacity={0.1}/>
            </linearGradient>
            <linearGradient id="colorSecurity" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="var(--silver-400)" stopOpacity={0.8}/>
              <stop offset="95%" stopColor="var(--silver-400)" stopOpacity={0.1}/>
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--silver-500)" opacity={0.2} />
          <XAxis dataKey="month" stroke="var(--silver-500)" />
          <YAxis stroke="var(--silver-500)" />
          <Tooltip 
            contentStyle={{ 
              backgroundColor: 'var(--black)', 
              border: '1px solid var(--purple-500)',
              borderRadius: '8px' 
            }} 
          />
          <Area type="monotone" dataKey="compliance" stroke="var(--purple-500)" fillOpacity={1} fill="url(#colorCompliance)" strokeWidth={2} />
          <Area type="monotone" dataKey="security" stroke="var(--silver-400)" fillOpacity={1} fill="url(#colorSecurity)" strokeWidth={2} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};
// Animated Radar Chart
export const AnimatedRadarChart = () => {
  return (
    <div className="bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 rounded-2xl p-6 border border-purple-800/20">
      <h3 className="text-xl font-semibold text-white mb-4">System Metrics</h3>
      <ResponsiveContainer width="100%" height={300}>
        <RadarChart data={radarData}>
          <PolarGrid stroke="var(--silver-500)" strokeDasharray="3 3" />
          <PolarAngleAxis dataKey="subject" stroke="var(--silver-500)" />
          <PolarRadiusAxis angle={90} domain={[0, 150]} stroke="var(--silver-500)" />
          <Radar name="Current" dataKey="A" stroke="var(--purple-500)" fill="var(--purple-500)" fillOpacity={0.6} />
          <Radar name="Target" dataKey="B" stroke="var(--silver-400)" fill="var(--silver-400)" fillOpacity={0.3} />
          <Legend />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
};

// Composed Chart with Bar and Line
export const ComposedDashboardChart = () => {
  return (
    <div className="bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 rounded-2xl p-6 border border-purple-800/20">
      <h3 className="text-xl font-semibold text-white mb-4">Revenue & Users</h3>
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--silver-500)" opacity={0.2} />
          <XAxis dataKey="month" stroke="var(--silver-500)" />
          <YAxis yAxisId="left" stroke="var(--silver-500)" />
          <YAxis yAxisId="right" orientation="right" stroke="var(--silver-500)" />
          <Tooltip 
            contentStyle={{ 
              backgroundColor: 'var(--black)', 
              border: '1px solid var(--purple-500)',
              borderRadius: '8px' 
            }} 
          />
          <Legend />
          <Bar yAxisId="left" dataKey="users" fill="var(--purple-500)" radius={[8, 8, 0, 0]} />
          <Line yAxisId="right" type="monotone" dataKey="performance" stroke="var(--silver-400)" strokeWidth={3} dot={{ fill: 'var(--silver-400)', r: 6 }} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
};