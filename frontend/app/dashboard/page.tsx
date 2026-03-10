'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Activity,
  Users,
  DollarSign,
  Shield,
  AlertCircle,
  CheckCircle2,
  ArrowUpRight,
  ArrowDownRight,
  BarChart3,
  FileText,
  Settings,
  Bell,
  Search,
  Menu,
  X,
  Zap,
  Globe,
} from 'lucide-react';
import { AuroraBackground } from '@/components/ui/backgrounds/aurora-background';
import { useAuthStore } from '@/lib/stores/auth.store';
import { cn } from '@/lib/utils';

const INITIAL_LIVE_DATA_POINTS = [42, 48, 54, 58, 63, 60, 66, 69, 64, 71, 75, 72, 78, 81, 76, 83, 79, 86, 84, 90];

// Animated Stats Card Component
const StatsCard = ({ 
  title, 
  value, 
  change, 
  trend, 
  icon: Icon,
  color 
}: any) => {  const [isHovered, setIsHovered] = useState(false);
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ scale: 1.02 }}
      onHoverStart={() => setIsHovered(true)}
      onHoverEnd={() => setIsHovered(false)}
      className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 p-6 border border-purple-800/20"
    >
      {/* Animated background gradient */}
      <motion.div
        className={cn(
          "absolute inset-0 opacity-20",
          color
        )}
        animate={{
          background: isHovered 
            ? `radial-gradient(circle at 50% 50%, ${color === 'purple' ? '#8B5CF6' : '#C0C0C0'} 0%, transparent 70%)`
            : 'transparent'
        }}
        transition={{ duration: 0.3 }}
      />
      
      <div className="relative z-10">
        <div className="flex items-center justify-between mb-4">
          <div className="p-2 bg-purple-600/10 rounded-lg">
            <Icon className="w-5 h-5 text-purple-400" />
          </div>
          {trend === 'up' ? (
            <ArrowUpRight className="w-5 h-5 text-green-400" />
          ) : (
            <ArrowDownRight className="w-5 h-5 text-red-400" />
          )}
        </div>        
        <p className="text-sm text-gray-400 mb-1">{title}</p>
        <p className="text-3xl font-bold text-white">{value}</p>
        <p className={cn(
          "text-sm mt-2",
          trend === 'up' ? 'text-green-400' : 'text-red-400'
        )}>
          {change} from last month
        </p>
      </div>
    </motion.div>
  );
};

// Activity Feed Item
const ActivityItem = ({ activity, index }: any) => {
  const message = activity.message ?? activity.title;

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.1 }}
      className="flex items-start space-x-3 p-3 hover:bg-purple-900/10 rounded-lg transition-colors"
    >
      <div className={cn(
        "p-2 rounded-full",
        activity.type === 'success' ? 'bg-green-900/20' : 
        activity.type === 'warning' ? 'bg-yellow-900/20' : 
        'bg-purple-900/20'
      )}>
        {activity.type === 'success' ? (
          <CheckCircle2 className="w-4 h-4 text-green-400" />
        ) : activity.type === 'warning' ? (
          <AlertCircle className="w-4 h-4 text-yellow-400" />
        ) : (
          <Activity className="w-4 h-4 text-purple-400" />
        )}
      </div>
      <div className="flex-1">
        <p className="text-sm text-gray-300">{message}</p>
        <p className="text-xs text-gray-500 mt-1">{activity.time}</p>
      </div>
    </motion.div>
  );
};

// Chart Component
const ChartSection = () => {
  const chartData = [65, 78, 90, 67, 84, 93, 73];
  
  return (
    <div className="bg-gray-900/50 backdrop-blur-sm rounded-2xl p-6 border border-gray-800">
      <div className="flex justify-between items-center mb-6">
        <h3 className="text-lg font-semibold text-white">Performance Metrics</h3>
        <div className="flex space-x-2">
          <button className="px-3 py-1 text-xs bg-purple-600/20 text-purple-400 rounded-lg hover:bg-purple-600/30 transition-colors">
            Week
          </button>
          <button className="px-3 py-1 text-xs text-gray-400 hover:bg-gray-800 rounded-lg transition-colors">
            Month
          </button>
          <button className="px-3 py-1 text-xs text-gray-400 hover:bg-gray-800 rounded-lg transition-colors">
            Year
          </button>
        </div>
      </div>
      <div className="h-64 flex items-end justify-between space-x-2">
        {chartData.map((value, index) => (
          <motion.div
            key={index}
            initial={{ height: 0 }}
            animate={{ height: `${value}%` }}
            transition={{ 
              delay: index * 0.05,
              type: "spring",
              stiffness: 100 
            }}
            className="flex-1 bg-gradient-to-t from-purple-600 to-purple-400 rounded-t-lg hover:from-purple-500 hover:to-purple-300 transition-colors relative group"
          >
            <div className="absolute -top-8 left-1/2 transform -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity">
              <span className="text-xs text-purple-300 font-semibold">{value}%</span>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
};

// Radial Progress Chart Component
const RadialChart = ({ value, label, color: _color }: any) => {
  const circumference = 2 * Math.PI * 45;
  const strokeDashoffset = circumference - (value / 100) * circumference;
  
  return (
    <div className="relative w-32 h-32">
      <svg className="transform -rotate-90 w-32 h-32">
        {/* Background circle */}
        <circle
          cx="64"
          cy="64"
          r="45"
          stroke="rgb(55, 48, 163, 0.1)"
          strokeWidth="10"
          fill="none"
        />
        {/* Progress circle */}
        <motion.circle
          cx="64"
          cy="64"
          r="45"
          stroke="url(#gradient)"
          strokeWidth="10"
          fill="none"
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset }}
          strokeDasharray={circumference}
          strokeLinecap="round"
          transition={{ duration: 1.5, ease: "easeOut" }}
        />
        <defs>
          <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#8B5CF6" />
            <stop offset="100%" stopColor="#C0C0C0" />
          </linearGradient>
        </defs>
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold text-white">{value}%</span>
        <span className="text-xs text-gray-400">{label}</span>
      </div>
    </div>
  );
};
// Live Data Stream Component (simulating real-time data)
const LiveDataStream = () => {
  const [dataPoints, setDataPoints] = useState<number[]>(INITIAL_LIVE_DATA_POINTS);

  useEffect(() => {
    const interval = setInterval(() => {
      setDataPoints(prev => {
        const nextPoint = Math.max(10, Math.min(95, prev[prev.length - 1] + (Math.random() * 18 - 9)));
        const newData = [...prev.slice(1), Number(nextPoint.toFixed(2))];
        return newData;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const chartPoints = dataPoints.map((point, i) => [
    Number(((i / (dataPoints.length - 1)) * 100).toFixed(2)),
    Number((100 - point).toFixed(2)),
  ]);
  const linePath = chartPoints.length > 0
    ? `M ${chartPoints[0][0]},${chartPoints[0][1]} L ${chartPoints.slice(1).map(([x, y]) => `${x},${y}`).join(' L ')}`
    : '';
  const areaPath = chartPoints.length > 0
    ? `M 0,100 L ${chartPoints.map(([x, y]) => `${x},${y}`).join(' L ')} L 100,100 Z`
    : '';

  return (
    <div className="bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 rounded-2xl p-6 border border-purple-800/20">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">Live Activity</h3>
        <div className="flex items-center space-x-2">
          <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
          <span className="text-xs text-green-400">Live</span>
        </div>
      </div>
      
      <div className="h-32 relative">
        <svg className="w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <linearGradient id="gradient2" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#8B5CF6" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#8B5CF6" stopOpacity="0.1" />
            </linearGradient>
            <filter id="glow">
              <feGaussianBlur stdDeviation="4" result="coloredBlur"/>
              <feMerge>
                <feMergeNode in="coloredBlur"/>
                <feMergeNode in="SourceGraphic"/>
              </feMerge>
            </filter>
          </defs>          
          <motion.path
            d={linePath}
            fill="none"
            stroke="url(#gradient2)"
            strokeWidth="2"
            filter="url(#glow)"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 0.5 }}
          />
          <motion.path
            d={areaPath}
            fill="url(#gradient2)"
            opacity="0.2"
          />
        </svg>
      </div>
    </div>
  );
};

// Main Dashboard Component
export default function DashboardPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading, checkAuthStatus } = useAuthStore();
  const [sidebarOpen, setSidebarOpen] = useState(true);

  useEffect(() => {
    checkAuthStatus();
  }, [checkAuthStatus]);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace('/login');
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading) {
    return <div className="min-h-screen bg-gray-950 text-white flex items-center justify-center">Loading dashboard...</div>;
  }

  if (!isAuthenticated) {
    return null;
  }
  
  const stats = [
    { title: 'Total Revenue', value: '$124,563', change: '+12.5%', trend: 'up', icon: DollarSign },
    { title: 'Active Users', value: '8,549', change: '+23.1%', trend: 'up', icon: Users },
    { title: 'Compliance Score', value: '98.2%', change: '+2.4%', trend: 'up', icon: Shield },
    { title: 'Active Alerts', value: '12', change: '-8.3%', trend: 'down', icon: AlertCircle },
  ];
  const activities = [
    { type: 'success', title: 'New compliance rule added', time: '2 minutes ago' },
    { type: 'warning', title: 'Review required for Policy #2847', time: '15 minutes ago' },
    { type: 'info', title: 'System backup completed', time: '1 hour ago' },
    { type: 'success', title: 'All checks passed for Q4 audit', time: '3 hours ago' },
  ];

  return (
    <div className="min-h-screen bg-gray-950">
      {/* Background Effect */}
      <AuroraBackground className="fixed inset-0 opacity-30" />
      
      {/* Main Content */}
      <div className="relative z-10">
        {/* Top Navigation */}
        <div className="border-b border-purple-900/20 bg-gray-950/80 backdrop-blur-xl">
          <div className="flex items-center justify-between px-6 py-4">
            <div className="flex items-center space-x-4">
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="text-gray-400 hover:text-white"
                aria-label={sidebarOpen ? 'Close navigation menu' : 'Open navigation menu'}
              >
                {sidebarOpen ? <X size={24} /> : <Menu size={24} />}
              </button>
              <h1 className="text-2xl font-bold text-white">Dashboard</h1>
            </div>
            
            <div className="flex items-center space-x-4">
              {/* Search Bar */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
                <input
                  type="text"
                  placeholder="Search..."
                  aria-label="Search dashboard"
                  className="pl-10 pr-4 py-2 bg-gray-900 border border-purple-800/20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-purple-600"
                />
              </div>              
              {/* Notifications */}
              <button className="relative p-2 text-gray-400 hover:text-white" aria-label="Open notifications">
                <Bell size={20} />
                <span className="absolute top-0 right-0 w-2 h-2 bg-purple-500 rounded-full" />
              </button>
              
              {/* Settings */}
              <button className="p-2 text-gray-400 hover:text-white" aria-label="Open dashboard settings">
                <Settings size={20} />
              </button>
              
              {/* Profile */}
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-purple-600 to-purple-400" />
            </div>
          </div>
        </div>

        <div className="flex">
          {/* Sidebar */}
          <AnimatePresence>
            {sidebarOpen && (
              <motion.aside
                initial={{ x: -300 }}
                animate={{ x: 0 }}
                exit={{ x: -300 }}
                className="w-64 h-[calc(100vh-73px)] bg-gray-900/50 backdrop-blur-xl border-r border-purple-900/20 p-4"
              >
                <nav className="space-y-2">
                  {[
                    { icon: BarChart3, label: 'Analytics', active: true },
                    { icon: FileText, label: 'Reports', active: false },
                    { icon: Shield, label: 'Compliance', active: false },
                    { icon: Users, label: 'Team', active: false },
                    { icon: Globe, label: 'Global View', active: false },
                    { icon: Zap, label: 'Automation', active: false },
                  ].map((item, index) => (
                    <motion.button
                      key={item.label}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: index * 0.1 }}                      className={cn(
                        "w-full flex items-center space-x-3 px-3 py-2 rounded-lg transition-colors",
                        item.active
                          ? "bg-purple-600/20 text-purple-400"
                          : "text-gray-400 hover:bg-purple-900/10 hover:text-white"
                      )}
                    >
                      <item.icon size={18} />
                      <span className="text-sm">{item.label}</span>
                    </motion.button>
                  ))}
                </nav>
              </motion.aside>
            )}
          </AnimatePresence>

          {/* Main Content */}
          <main className="flex-1 p-6 overflow-auto">
            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              {stats.map((stat, index) => (
                <StatsCard key={index} {...stat} color="purple" />
              ))}
            </div>

            {/* Charts Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
              <ChartSection />
              <LiveDataStream />
            </div>

            {/* Bottom Section */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Activity Feed */}
              <div className="lg:col-span-2 bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 rounded-2xl p-6 border border-purple-800/20">
                <h3 className="text-xl font-semibold text-white mb-4">Recent Activity</h3>
                <div className="space-y-2">
                  {activities.map((activity, index) => (
                    <ActivityItem key={index} activity={activity} index={index} />
                  ))}
                </div>
              </div>
              {/* Progress Indicators */}
              <div className="bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 rounded-2xl p-6 border border-purple-800/20">
                <h3 className="text-xl font-semibold text-white mb-6">System Health</h3>
                <div className="space-y-6">
                  <div className="flex justify-center">
                    <RadialChart value={92} label="CPU Usage" color="purple" />
                  </div>
                  <div className="space-y-3">
                    <div>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="text-gray-400">Memory</span>
                        <span className="text-white">67%</span>
                      </div>
                      <div className="w-full bg-gray-800 rounded-full h-2">
                        <motion.div 
                          initial={{ width: 0 }}
                          animate={{ width: '67%' }}
                          transition={{ duration: 1, ease: "easeOut" }}
                          className="h-2 bg-gradient-to-r from-purple-600 to-purple-400 rounded-full"
                        />
                      </div>
                    </div>
                    <div>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="text-gray-400">Storage</span>
                        <span className="text-white">84%</span>
                      </div>
                      <div className="w-full bg-gray-800 rounded-full h-2">
                        <motion.div 
                          initial={{ width: 0 }}
                          animate={{ width: '84%' }}
                          transition={{ duration: 1.2, ease: "easeOut" }}
                          className="h-2 bg-gradient-to-r from-purple-600 to-silver-400 rounded-full"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}