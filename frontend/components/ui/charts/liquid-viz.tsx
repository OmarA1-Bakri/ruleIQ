'use client';

import React, { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';

// LIQUID DATA VISUALIZATION - Data as flowing liquid
export const LiquidDataVisualization = ({ data = [] }: { data?: number[] }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number | null>(null);
  const [_particles, _setParticles] = useState<any[]>([]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    canvas.width = canvas.offsetWidth;
    canvas.height = canvas.offsetHeight;

    // Create liquid particles
    const liquidParticles: any[] = [];
    const particleCount = 500;
    
    for (let i = 0; i < particleCount; i++) {
      liquidParticles.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        vx: (Math.random() - 0.5) * 2,
        vy: (Math.random() - 0.5) * 2,
        radius: Math.random() * 3 + 1,
        color: `hsla(${263 + Math.random() * 30}, 72%, ${50 + Math.random() * 20}%, ${0.3 + Math.random() * 0.5})`,
        life: Math.random(),
      });
    }

    setParticles(liquidParticles);

    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      
      liquidParticles.forEach(particle => {
        // Update particle position
        particle.x += particle.vx;
        particle.y += particle.vy;
        
        // Boundary collision
        if (particle.x <= 0 || particle.x >= canvas.width) particle.vx *= -1;
        if (particle.y <= 0 || particle.y >= canvas.height) particle.vy *= -1;
        
        // Draw particle
        ctx.beginPath();
        ctx.arc(particle.x, particle.y, particle.radius, 0, Math.PI * 2);
        ctx.fillStyle = particle.color;
        ctx.fill();
      });
      
      animationRef.current = requestAnimationFrame(animate);
    };
    
    animate();
    
    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [data]);

  return (
    <motion.div className="relative w-full h-64">
      <canvas 
        ref={canvasRef} 
        className="w-full h-full rounded-lg bg-gradient-to-br from-purple-900/20 to-purple-600/20"
      />
    </motion.div>
  );
};

export default LiquidDataVisualization;
