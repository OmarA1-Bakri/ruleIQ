'use client';

import { motion } from 'framer-motion';
import { useMemo } from 'react';
import { cn } from '@/lib/utils';

type SparklesBackgroundProps = {
  id?: string;
  className?: string;
  background?: string;
  minSize?: number;
  maxSize?: number;
  particleDensity?: number;
  particleColor?: string;
};

export function SparklesBackground({
  id = 'sparkles',
  className,
  background = 'transparent',
  minSize = 0.6,
  maxSize = 1.4,
  particleDensity = 100,
  particleColor = '#2C7A7B', // teal-600
}: SparklesBackgroundProps) {
  const particles = useMemo(() => {
    return Array.from({ length: particleDensity }, (_, i) => ({
      id: i,
      x: Math.random() * 100,
      y: Math.random() * 100,
      size: Math.random() * (maxSize - minSize) + minSize,
      animationDelay: Math.random() * 3,
    }));
  }, [particleDensity, minSize, maxSize]);

  return (
    <div
      id={id}
      className={cn('absolute inset-0 overflow-hidden', className)}
      style={{ background }}
    >
      {particles.map((particle) => (
        <motion.div
          key={particle.id}
          className="absolute rounded-full"
          style={{
            left: `${particle.x}%`,
            top: `${particle.y}%`,
            width: `${particle.size}px`,
            height: `${particle.size}px`,
            backgroundColor: particleColor,
            boxShadow: `0 0 ${particle.size * 2}px ${particleColor}`,
          }}
          animate={{
            opacity: [0, 1, 0],
            scale: [0.8, 1.2, 0.8],
          }}
          transition={{
            duration: 3,
            repeat: Infinity,
            delay: particle.animationDelay,
            ease: 'easeInOut',
          }}
        />
      ))}
    </div>
  );
}
