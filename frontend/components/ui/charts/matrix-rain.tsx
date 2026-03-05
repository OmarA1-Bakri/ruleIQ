'use client';

import React, { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';

// MATRIX RAIN DATA VISUALIZATION
export const MatrixRainVisualization = ({ data: _data = [] }: { data?: number[] }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [metrics, setMetrics] = useState({ 
    dataFlow: 87, 
    security: 92, 
    performance: 78 
  });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    canvas.width = canvas.offsetWidth;
    canvas.height = canvas.offsetHeight;

    const chars = '01アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン';
    const fontSize = 14;
    const columns = canvas.width / fontSize;
    const drops: number[] = [];

    for (let i = 0; i < columns; i++) {
      drops[i] = Math.random() * -100;
    }

    const draw = () => {
      ctx.fillStyle = 'rgba(10, 10, 11, 0.05)';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      ctx.font = `${fontSize}px monospace`;
      
      for (let i = 0; i < drops.length; i++) {
        const text = chars[Math.floor(Math.random() * chars.length)] ?? '0';
        const x = i * fontSize;
        const y = (drops[i] ?? 0) * fontSize;
        // Color gradient based on position
        const gradient = ctx.createLinearGradient(0, y - fontSize * 10, 0, y);
        gradient.addColorStop(0, 'rgba(139, 92, 246, 0)');
        gradient.addColorStop(0.5, 'rgba(139, 92, 246, 0.5)');
        gradient.addColorStop(1, 'rgba(192, 192, 192, 1)');
        
        ctx.fillStyle = gradient;
        ctx.fillText(text, x, y);

        if (y > canvas.height && Math.random() > 0.975) {
          drops[i] = 0;
        }
        drops[i] = (drops[i] ?? 0) + 1;
      }
    };

    const interval = setInterval(draw, 35);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      setMetrics({
        dataFlow: Math.floor(Math.random() * 20 + 80),
        security: Math.floor(Math.random() * 15 + 85),
        performance: Math.floor(Math.random() * 25 + 75),
      });
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="relative bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 rounded-2xl p-6 border border-purple-800/20 h-[400px] overflow-hidden">
      <canvas 
        ref={canvasRef} 
        className="absolute inset-0 w-full h-full"
      />
      
      <div className="relative z-10">
        <h3 className="text-xl font-semibold text-white mb-4">System Matrix</h3>
        
        <div className="grid grid-cols-3 gap-4 mt-8">
          {Object.entries(metrics).map(([key, value]) => (
            <motion.div
              key={key}
              className="bg-black/50 backdrop-blur-sm rounded-lg p-4 border border-purple-600/30"
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 0.3 }}
            >
              <p className="text-xs text-purple-400 capitalize">{key}</p>
              <motion.p 
                className="text-2xl font-bold text-white"
                animate={{ opacity: [0.5, 1] }}
                transition={{ duration: 0.5 }}
              >
                {value}%
              </motion.p>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
};