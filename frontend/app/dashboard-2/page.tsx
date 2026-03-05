'use client';

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { 
  Sparkles,
  Waves,
  Box,
  Cpu,
  ArrowRight,
} from 'lucide-react';
// Using neural theme instead of aurora background
import { ParticleSwarmChart } from '@/components/ui/charts/particle-swarm';
import { ThreeDDataOrb } from '@/components/ui/charts/3d-orb';
import { WaveDataVisualization } from '@/components/ui/charts/wave-viz';
import { MatrixRainVisualization } from '@/components/ui/charts/matrix-rain';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export default function ExtraordinaryDashboard() {
  const [activeView, setActiveView] = useState('overview');

  const visualizations = [
    {
      id: 'particles',
      title: 'Neural Network',
      icon: Sparkles,
      description: 'Live particle swarm visualization',
      component: ParticleSwarmChart,
    },
    {
      id: 'orb',
      title: 'Quantum State',
      icon: Box,
      description: '3D morphing data orb',
      component: ThreeDDataOrb,
    },    {
      id: 'wave',
      title: 'Data Flow',
      icon: Waves,
      description: 'Liquid wave dynamics',
      component: WaveDataVisualization,
    },
    {
      id: 'matrix',
      title: 'System Matrix',
      icon: Cpu,
      description: 'Matrix rain visualization',
      component: MatrixRainVisualization,
    },
  ];

  return (
    <div className="min-h-screen bg-black">
      {/* Neural network background gradient */}
      <div className="fixed inset-0 bg-gradient-to-br from-neural-purple-900/10 via-black to-black" />
      
      <div className="relative z-10">
        {/* Header */}
        <div className="border-b border-purple-900/20 bg-gray-950/80 backdrop-blur-xl">
          <div className="container mx-auto px-6 py-6">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold bg-gradient-to-r from-purple-400 to-silver-300 bg-clip-text text-transparent">
                  Extraordinary Dashboard
                </h1>
                <p className="text-gray-400 mt-1">Next-generation data visualization</p>
              </div>
              
              <div className="flex space-x-2">
                {['overview', 'detailed'].map((view) => (
                  <Button
                    key={view}
                    onClick={() => setActiveView(view)}
                    className={cn(
                      "capitalize",
                      activeView === view
                        ? "bg-purple-600 text-white"
                        : "bg-gray-800 text-gray-400 hover:text-white"
                    )}
                  >
                    {view}
                  </Button>
                ))}
              </div>
            </div>
          </div>
        </div>
        {/* Main Content */}
        <div className="container mx-auto px-6 py-8">
          {activeView === 'overview' ? (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {visualizations.map((viz, index) => (
                <motion.div
                  key={viz.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.1 }}
                >
                  <viz.component />
                </motion.div>
              ))}
            </div>
          ) : (
            <div className="space-y-6">
              {/* Navigation Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                {visualizations.map((viz, index) => (
                  <motion.div
                    key={viz.id}
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: index * 0.05 }}
                    className="bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 rounded-xl p-6 border border-purple-800/20 hover:border-purple-600/40 transition-all cursor-pointer group"
                  >
                    <viz.icon className="w-8 h-8 text-purple-400 mb-3 group-hover:text-purple-300 transition-colors" />
                    <h3 className="text-white font-semibold mb-1">{viz.title}</h3>
                    <p className="text-gray-400 text-sm">{viz.description}</p>
                    <ArrowRight className="w-4 h-4 text-purple-400 mt-3 group-hover:translate-x-1 transition-transform" />
                  </motion.div>
                ))}
              </div>
              
              {/* Full Width Visualizations */}
              <div className="space-y-6">
                <ParticleSwarmChart />
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <ThreeDDataOrb />
                  <MatrixRainVisualization />
                </div>
                <WaveDataVisualization />
              </div>
            </div>
          )}
          
          {/* Stats Footer */}
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5 }}
            className="mt-12 grid grid-cols-2 md:grid-cols-4 gap-4"
          >
            {[
              { label: 'Data Points', value: '1.2M', change: '+12%' },
              { label: 'Processing', value: '847 TB/s', change: '+8%' },
              { label: 'Nodes Active', value: '12,847', change: '+23%' },
              { label: 'Quantum State', value: '0.97φ', change: 'Stable' },
            ].map((stat, index) => (
              <div 
                key={index}
                className="bg-gray-900/50 backdrop-blur-sm rounded-lg p-4 border border-purple-900/20"
              >
                <p className="text-xs text-gray-400">{stat.label}</p>
                <p className="text-2xl font-bold text-white mt-1">{stat.value}</p>
                <p className="text-xs text-purple-400 mt-2">{stat.change}</p>
              </div>
            ))}
          </motion.div>
        </div>
      </div>
    </div>
  );
}