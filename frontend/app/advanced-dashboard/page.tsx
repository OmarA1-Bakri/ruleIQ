'use client';

import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  BarChart3,
  Network,
  TrendingUp,
  Layers,
  Activity,
  RefreshCw,
  Download,
  Settings,
} from 'lucide-react';
// Using neural theme instead of aurora background
import { EChartsTimeSeries, EChartsCandlestick } from '@/components/ui/charts/echarts-viz';
import { VegaLiteVisualization } from '@/components/ui/charts/vega-viz';
import { SigmaNetworkGraph } from '@/components/ui/charts/sigma-viz';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export default function AdvancedDashboard() {
  const [activeTab, setActiveTab] = useState('overview');
  const [apiStatus, setApiStatus] = useState<any>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    checkApiHealth();
  }, []);

  const checkApiHealth = async () => {
    try {
      const response = await fetch('http://localhost:8000/health');
      const data = await response.json();
      setApiStatus(data);
    } catch (error) {
      console.error('API not available:', error);
      setApiStatus({ status: 'offline' });
    }
  };

  const refreshData = () => {
    setRefreshKey(prev => prev + 1);
    checkApiHealth();
  };

  const tabs = [
    { id: 'overview', label: 'Overview', icon: BarChart3 },
    { id: 'timeseries', label: 'Time Series', icon: TrendingUp },
    { id: 'market', label: 'Market Data', icon: Activity },
    { id: 'network', label: 'Network', icon: Network },
    { id: 'analysis', label: 'Analysis', icon: Layers },
  ];
  return (
    <div className="min-h-screen bg-black">
      {/* Neural network background gradient */}
      <div className="fixed inset-0 bg-gradient-to-br from-neural-purple-900/10 via-black to-black" />
      
      <div className="relative z-10">
        {/* Header */}
        <div className="border-b border-purple-900/20 bg-gray-950/80 backdrop-blur-xl">
          <div className="container mx-auto px-6 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <h1 className="text-2xl font-bold bg-gradient-to-r from-purple-400 to-silver-300 bg-clip-text text-transparent">
                  Advanced Analytics Dashboard
                </h1>
                {apiStatus && (
                  <div className="flex items-center space-x-2">
                    <div className={cn(
                      "w-2 h-2 rounded-full",
                      apiStatus.status === 'healthy' ? 'bg-green-400' : 'bg-red-400'
                    )} />
                    <span className="text-xs text-gray-400">
                      API {apiStatus.status === 'healthy' ? 'Online' : 'Offline'}
                    </span>
                  </div>
                )}
              </div>
              
              <div className="flex items-center space-x-2">
                <Button
                  onClick={refreshData}
                  size="sm"
                  variant="ghost"
                  className="text-gray-400 hover:text-white"
                >
                  <RefreshCw className="w-4 h-4" />
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-gray-400 hover:text-white"
                >
                  <Download className="w-4 h-4" />
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-gray-400 hover:text-white"
                >
                  <Settings className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </div>
        </div>
        {/* Tab Navigation */}
        <div className="border-b border-purple-900/20 bg-gray-900/50">
          <div className="container mx-auto px-6">
            <div className="flex space-x-1">
              {tabs.map((tab) => {
                const Icon = tab.icon;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={cn(
                      "flex items-center space-x-2 px-4 py-3 text-sm font-medium transition-colors",
                      activeTab === tab.id
                        ? "text-purple-400 border-b-2 border-purple-400"
                        : "text-gray-400 hover:text-white"
                    )}
                  >
                    <Icon className="w-4 h-4" />
                    <span>{tab.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="container mx-auto px-6 py-8">
          {activeTab === 'overview' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6" key={refreshKey}>
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
              >
                <EChartsTimeSeries />
              </motion.div>
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
              >
                <VegaLiteVisualization />
              </motion.div>
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
                className="lg:col-span-2"
              >
                <SigmaNetworkGraph />
              </motion.div>
            </div>
          )}

          {activeTab === 'timeseries' && (
            <div key={refreshKey}>
              <EChartsTimeSeries />
            </div>
          )}

          {activeTab === 'market' && (
            <div key={refreshKey}>
              <EChartsCandlestick />
            </div>
          )}

          {activeTab === 'network' && (
            <div key={refreshKey}>
              <SigmaNetworkGraph />
            </div>
          )}

          {activeTab === 'analysis' && (
            <div key={refreshKey}>
              <VegaLiteVisualization />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}