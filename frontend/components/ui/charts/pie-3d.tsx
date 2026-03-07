'use client';

import React, { useState } from 'react';
import { motion } from 'framer-motion';

// 3D Pie Chart Component
export const PieChart3D = () => {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  
  const data = [
    { label: 'Compliance', value: 35, color: 'var(--purple-500)' },
    { label: 'Security', value: 25, color: 'var(--purple-500)' },
    { label: 'Performance', value: 20, color: 'var(--purple-400)' },
    { label: 'Infrastructure', value: 20, color: 'var(--purple-50)' },
  ];

  let startAngle = -90;
  
  return (
    <div className="bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 rounded-2xl p-6 border border-purple-800/20">
      <h3 className="text-xl font-semibold text-white mb-4">Resource Allocation</h3>
      
      <div className="relative">
        <svg width="300" height="200" className="mx-auto">
          <defs>
            <filter id="shadow">
              <feGaussianBlur in="SourceAlpha" stdDeviation="3"/>
              <feOffset dx="0" dy="4" result="offsetblur"/>
              <feComponentTransfer>
                <feFuncA type="linear" slope="0.3"/>
              </feComponentTransfer>
              <feMerge>
                <feMergeNode/>
                <feMergeNode in="SourceGraphic"/>
              </feMerge>
            </filter>
          </defs>
          
          {/* Shadow ellipse */}
          <ellipse cx="150" cy="120" rx="80" ry="20" fill="rgba(0,0,0,0.2)" />
          
          {data.map((segment, index) => {
            const angle = (segment.value / 100) * 360;
            const endAngle = startAngle + angle;
            const isHovered = hoveredIndex === index;            
            const path = describeArc(150, 100, 80, startAngle, endAngle);
            const _currentStartAngle = startAngle;
            startAngle = endAngle;

            return (
              <motion.g
                key={index}
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ 
                  opacity: 1, 
                  scale: isHovered ? 1.05 : 1,
                  y: isHovered ? -5 : 0
                }}
                transition={{ delay: index * 0.1 }}
                onMouseEnter={() => setHoveredIndex(index)}
                onMouseLeave={() => setHoveredIndex(null)}
              >
                <path
                  d={path}
                  fill={segment.color}
                  filter="url(#shadow)"
                  opacity={isHovered ? 1 : 0.9}
                />
                {/* 3D side effect */}
                <path
                  d={`${path} L 150,120 Z`}
                  fill={segment.color}
                  opacity="0.7"
                />
              </motion.g>
            );
          })}
        </svg>
        
        {/* Legend */}
        <div className="flex justify-center mt-6 space-x-4">
          {data.map((item, index) => (
            <motion.div
              key={index}
              className="flex items-center space-x-2"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
            >
              <div 
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: item.color }}
              />
              <span className="text-xs text-gray-400">{item.label}</span>
              <span className="text-xs font-semibold text-white">{item.value}%</span>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
};

// Helper function for arc path
function describeArc(x: number, y: number, radius: number, startAngle: number, endAngle: number) {
  const start = polarToCartesian(x, y, radius, endAngle);
  const end = polarToCartesian(x, y, radius, startAngle);
  const largeArcFlag = endAngle - startAngle <= 180 ? "0" : "1";
  return [
    "M", start.x, start.y,
    "A", radius, radius, 0, largeArcFlag, 0, end.x, end.y,
    "L", x, y,
    "Z"
  ].join(" ");
}

function polarToCartesian(centerX: number, centerY: number, radius: number, angleInDegrees: number) {
  const angleInRadians = (angleInDegrees - 90) * Math.PI / 180.0;
  return {
    x: centerX + (radius * Math.cos(angleInRadians)),
    y: centerY + (radius * Math.sin(angleInRadians))
  };
}