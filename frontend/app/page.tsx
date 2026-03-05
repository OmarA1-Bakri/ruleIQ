'use client';

import React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import {
  ArrowRight,
  Shield,
  Zap,
  BarChart3,
  Lock,
  Globe,
  Users,
  CheckCircle,
  TrendingUp,
  FileCheck,
  ChevronRight,
  Sparkles,
  Activity,
  Brain,
  Server,
} from 'lucide-react';

// Import the Neural Network Hero component
import Hero from '@/components/ui/neural-network-hero';
import PricingPreview from '@/components/ui/pricing-preview';
import { useAuthStore } from '@/lib/stores/auth.store';
import { Header } from '@/components/ui/header';

// Feature Card Component
function FeatureCard({ icon: Icon, title, description, delay = 0 }: {
  icon: React.ComponentType<any>;
  title: string;
  description: string;
  delay?: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay }}
      className="group relative"
    >
      <div className="absolute -inset-0.5 bg-gradient-to-r from-neural-purple-600 to-neural-purple-400 
                      rounded-3xl opacity-0 group-hover:opacity-20 transition duration-500 blur-xl" />
      <div className="relative bg-black/50 border border-neural-purple-500/10 rounded-3xl p-8
                      backdrop-blur-sm transition-all duration-300
                      hover:border-neural-purple-500/30 hover:-translate-y-1">
        <div className="w-12 h-12 rounded-2xl bg-neural-purple-500/10 
                        flex items-center justify-center mb-6
                        group-hover:bg-neural-purple-500/20 transition-colors">
          <Icon className="w-6 h-6 text-neural-purple-400" />
        </div>
        <h3 className="text-xl font-light text-white mb-3">
          {title}
        </h3>
        <p className="text-sm font-light text-white/60 leading-relaxed">
          {description}
        </p>
      </div>
    </motion.div>
  );
}

// Metric Card Component
function MetricCard({ value, label, icon: Icon }: {
  value: string;
  label: string;
  icon: React.ComponentType<any>;
}) {
  return (
    <div className="text-center group">
      <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl 
                      bg-neural-purple-500/10 mb-4 group-hover:bg-neural-purple-500/20 
                      transition-all duration-300">
        <Icon className="w-8 h-8 text-neural-purple-400" />
      </div>
      <div className="text-4xl font-extralight text-white mb-2">
        {value}
      </div>
      <div className="text-sm font-light text-white/60">
        {label}
      </div>
    </div>
  );
}

// Main Page Component
export default function HomePage() {
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();
  
  return (
    <div className="relative min-h-screen bg-black overflow-hidden">
      {/* Background gradient */}
      <div className="fixed inset-0 bg-gradient-to-br from-neural-purple-900/20 via-black to-black" />
      
      {/* Header */}
      <Header />
      
      {/* Neural Network Hero Section */}
      <Hero 
        title="Automate Compliance with AI Intelligence"
        description="Transform your regulatory processes with RuleIQ's advanced AI-powered compliance automation platform. Ensure accuracy, reduce risk, and save time."
        badgeText="Next-Gen Compliance Platform"
        badgeLabel="NEW"
        ctaButtons={[
          { 
            text: "Start Free Trial", 
            href: isAuthenticated ? "/dashboard" : "/auth/sign-up",
            primary: true 
          },
          { 
            text: "View Demo", 
            href: "#demo" 
          }
        ]}
        microDetails={[
          "AI-Powered Analysis",
          "Real-time Monitoring", 
          "99.9% Uptime"
        ]}
      />
      
      {/* Features Section */}
      <section id="features" className="relative py-24 px-6">
        <div className="mx-auto max-w-7xl">
          <div className="text-center mb-16">
            <motion.h2
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="text-5xl font-extralight tracking-tight text-white mb-6"
            >
              Enterprise-Grade Features
            </motion.h2>
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.1 }}
              className="text-lg font-light text-white/60 max-w-3xl mx-auto"
            >
              Built for modern compliance teams who demand excellence
            </motion.p>
          </div>
          
          {/* Features Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            <FeatureCard
              icon={Shield}
              title="Real-time Risk Assessment"
              description="AI-powered analysis identifies compliance risks before they become issues"
              delay={0}
            />
            <FeatureCard
              icon={Zap}
              title="Instant Policy Updates"
              description="Stay current with automatic regulatory change detection and implementation"
              delay={0.1}
            />
            <FeatureCard
              icon={BarChart3}
              title="Advanced Analytics"
              description="Deep insights into compliance performance with predictive modeling"
              delay={0.2}
            />
            <FeatureCard
              icon={Lock}
              title="Bank-Grade Security"
              description="End-to-end encryption and SOC 2 Type II compliance for your data"
              delay={0.3}
            />
            <FeatureCard
              icon={Globe}
              title="Global Compliance"
              description="Multi-jurisdiction support for international regulatory requirements"
              delay={0.4}
            />
            <FeatureCard
              icon={Users}
              title="Team Collaboration"
              description="Seamless workflow management for distributed compliance teams"
              delay={0.5}
            />
          </div>
        </div>
      </section>

      {/* Metrics Section */}
      <section className="relative py-24 px-6 bg-gradient-to-b from-black to-neural-purple-900/10">
        <div className="mx-auto max-w-7xl">
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            transition={{ duration: 0.8 }}
            className="grid grid-cols-2 lg:grid-cols-4 gap-8"
          >
            <MetricCard
              icon={CheckCircle}
              value="99.9%"
              label="Compliance Rate"
            />
            <MetricCard
              icon={TrendingUp}
              value="80%"
              label="Time Saved"
            />
            <MetricCard
              icon={Users}
              value="10K+"
              label="Active Users"
            />
            <MetricCard
              icon={FileCheck}
              value="500K+"
              label="Policies Managed"
            />
          </motion.div>
        </div>
      </section>

      {/* How It Works Section */}
      <section className="relative py-24 px-6">
        <div className="mx-auto max-w-7xl">
          <div className="text-center mb-16">
            <motion.h2
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="text-5xl font-extralight tracking-tight text-white mb-6"
            >
              How It Works
            </motion.h2>
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.1 }}
              className="text-lg font-light text-white/60 max-w-3xl mx-auto"
            >
              Get started in minutes with our intelligent compliance platform
            </motion.p>
          </div>

          <div className="grid lg:grid-cols-3 gap-8 lg:gap-12">
            {[
              {
                step: "01",
                title: "Connect Your Systems",
                description: "Seamlessly integrate with your existing tools and data sources",
                icon: Server,
              },
              {
                step: "02",
                title: "AI Analysis",
                description: "Our AI engine analyzes your compliance landscape and identifies gaps",
                icon: Brain,
              },
              {
                step: "03",
                title: "Automated Compliance",
                description: "Receive real-time alerts and automated compliance recommendations",
                icon: Activity,
              },
            ].map((item, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: index * 0.1 }}
                className="relative"
              >
                <div className="text-neural-purple-400/20 text-6xl font-extralight mb-4">
                  {item.step}
                </div>
                <div className="flex items-center gap-4 mb-4">
                  <div className="w-12 h-12 rounded-2xl bg-neural-purple-500/10 
                                  flex items-center justify-center">
                    <item.icon className="w-6 h-6 text-neural-purple-400" />
                  </div>
                  <h3 className="text-2xl font-light text-white">
                    {item.title}
                  </h3>
                </div>
                <p className="text-white/60 font-light">
                  {item.description}
                </p>
                {index < 2 && (
                  <ChevronRight className="hidden lg:block absolute top-1/2 -right-6 
                                          w-8 h-8 text-neural-purple-400/20" />
                )}
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <PricingPreview />

      {/* CTA Section */}
      <section className="relative py-24 px-6">
        <div className="mx-auto max-w-4xl text-center">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5 }}
            className="relative"
          >
            <div className="absolute -inset-4 bg-gradient-to-r from-neural-purple-600/20 to-neural-purple-400/20 
                            rounded-3xl blur-3xl" />
            <div className="relative bg-gradient-to-br from-neural-purple-900/50 to-black 
                            border border-neural-purple-500/20 rounded-3xl p-12">
              <Sparkles className="w-12 h-12 text-neural-purple-400 mx-auto mb-6" />
              <h2 className="text-4xl font-extralight tracking-tight text-white mb-6">
                Ready to Transform Your Compliance?
              </h2>
              <p className="text-lg font-light text-white/75 mb-8 max-w-2xl mx-auto">
                Join thousands of organizations using RuleIQ to automate and streamline their compliance processes.
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <Link
                  href={isAuthenticated ? "/dashboard" : "/auth/sign-up"}
                  className="inline-flex items-center justify-center gap-2 
                             bg-gradient-to-r from-neural-purple-500 to-neural-purple-600
                             text-white px-6 py-3 rounded-2xl font-light tracking-tight
                             transition-all duration-300 
                             hover:from-neural-purple-400 hover:to-neural-purple-500
                             hover:-translate-y-0.5 hover:shadow-purple-md"
                >
                  Get Started Free
                  <ArrowRight className="w-4 h-4" />
                </Link>
                <button
                  onClick={() => router.push('/contact')}
                  className="inline-flex items-center justify-center
                             bg-transparent text-white px-6 py-3 rounded-2xl 
                             font-light tracking-tight border border-white/10
                             transition-all duration-300
                             hover:bg-white/5 hover:border-white/20"
                >
                  Schedule Demo
                </button>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Footer */}
      <footer className="relative border-t border-white/5 py-12 px-6">
        <div className="mx-auto max-w-7xl">
          <div className="flex flex-col md:flex-row justify-between items-center gap-4">
            <p className="text-sm font-light text-white/40">
              © 2024 RuleIQ. All rights reserved.
            </p>
            <div className="flex gap-6">
              <Link href="/privacy" className="text-sm font-light text-white/40 hover:text-white/60 transition-colors">
                Privacy Policy
              </Link>
              <Link href="/terms" className="text-sm font-light text-white/40 hover:text-white/60 transition-colors">
                Terms of Service
              </Link>
              <Link href="/contact" className="text-sm font-light text-white/40 hover:text-white/60 transition-colors">
                Contact
              </Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}