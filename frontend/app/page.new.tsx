'use client';

import { motion, useScroll, useTransform } from 'framer-motion';
import {
  ArrowRight,
  Shield,
  Zap,
  BarChart3,
  Lock,
  Globe,
  CheckCircle,
  Star,
  TrendingUp,
  Users,
  FileCheck,
  Crown,
} from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import React, { useRef } from 'react';

import { Button } from '@/components/ui/button';
import { useAuthStore } from '@/lib/stores/auth.store';
import { cn } from '@/lib/utils';

// Hero Section with Dark Mode and Silver Accents
const HeroSection = () => {
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();
  const containerRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ['start start', 'end start'],
  });

  const y = useTransform(scrollYProgress, [0, 1], ['0%', '50%']);
  const opacity = useTransform(scrollYProgress, [0, 1], [1, 0]);

  return (
    <section
      id="hero-section"
      ref={containerRef}
      className="relative flex min-h-screen items-center justify-center overflow-hidden bg-gradient-to-br from-gray-950 via-purple-950/20 to-gray-950"
    >
      {/* Dark gradient background with purple hints */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-purple-900/10 via-gray-950 to-black" />

      {/* Animated silver grid pattern */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#1a1a1a_1px,transparent_1px),linear-gradient(to_bottom,#1a1a1a_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)]" />

      {/* Purple glow orbs */}
      <div className="absolute inset-0">
        {[...Array(3)].map((_, i) => (
          <motion.div
            key={i}
            className="absolute h-96 w-96 rounded-full bg-purple-600/20 blur-3xl"
            animate={{
              x: [0, 100, -100, 0],
              y: [0, -100, 100, 0],
            }}
            transition={{
              duration: 20 + i * 5,
              repeat: Infinity,
              ease: 'linear',
            }}
            style={{
              left: `${20 + i * 30}%`,
              top: `${10 + i * 20}%`,
            }}
          />
        ))}
      </div>

      {/* Content */}
      <motion.div
        style={{ y, opacity }}
        className="relative z-10 mx-auto max-w-7xl px-4 text-center sm:px-6 lg:px-8"
      >
        {/* Premium badge */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="mb-8 inline-flex items-center rounded-full border border-purple-500/30 bg-purple-950/50 px-4 py-2 backdrop-blur-sm"
        >
          <Crown className="mr-2 h-4 w-4 text-purple-400" />
          <span className="text-sm font-medium text-purple-300">
            AI-Powered Compliance Excellence
          </span>
        </motion.div>

        {/* Main heading with gradient */}
        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="mb-6 text-5xl font-bold tracking-tight text-white sm:text-6xl lg:text-7xl"
        >
          <span className="bg-gradient-to-r from-white via-purple-200 to-white bg-clip-text text-transparent">
            Transform
          </span>
          <br />
          <span className="bg-gradient-to-r from-purple-400 to-purple-600 bg-clip-text text-transparent">
            Your Compliance
          </span>
        </motion.h1>

        {/* Subheading */}
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="mx-auto mb-10 max-w-2xl text-lg text-gray-300 sm:text-xl"
        >
          Automate compliance management with AI. Cut costs by 60%, reduce audit prep by 75%, 
          and achieve 99.9% accuracy across 50+ frameworks.
        </motion.p>

        {/* CTA Buttons */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="flex flex-col items-center justify-center gap-4 sm:flex-row"
        >
          <Button
            size="lg"
            className="group relative overflow-hidden bg-gradient-to-r from-purple-600 to-purple-700 px-8 py-6 text-base font-semibold text-white shadow-xl transition-all hover:shadow-purple-500/25 hover:shadow-2xl"
            onClick={() => {
              if (isAuthenticated) {
                router.push('/dashboard');
              } else {
                router.push('/signup');
              }
            }}
          >
            <span className="relative z-10 flex items-center">
              Start Free AI Assessment
              <ArrowRight className="ml-2 h-5 w-5 transition-transform group-hover:translate-x-1" />
            </span>
            <div className="absolute inset-0 bg-gradient-to-r from-purple-700 to-purple-800 opacity-0 transition-opacity group-hover:opacity-100" />
          </Button>

          <div className="flex items-center gap-3">
            {isAuthenticated ? (
              <Link href="/dashboard">
                <Button
                  size="lg"
                  variant="outline"
                  className="border-gray-700 bg-gray-900/50 text-gray-300 backdrop-blur-sm hover:bg-gray-800/50 hover:text-white"
                >
                  Go to Dashboard
                </Button>
              </Link>
            ) : (
              <Link href="/signin">
                <Button
                  size="lg"
                  variant="outline"
                  className="border-gray-700 bg-gray-900/50 text-gray-300 backdrop-blur-sm hover:bg-gray-800/50 hover:text-white"
                >
                  Already have an account?
                </Button>
              </Link>
            )}
            <Button
              size="lg"
              variant="ghost"
              className="text-gray-400 hover:text-white"
              onClick={() => router.push('/demo')}
            >
              Watch Demo
            </Button>
          </div>
        </motion.div>

        {/* Trust badges */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.4 }}
          className="mt-12 flex flex-wrap items-center justify-center gap-6"
        >
          {[
            { icon: Shield, label: 'SOC 2 Certified' },
            { icon: Lock, label: 'Bank-Grade Security' },
            { icon: Globe, label: 'GDPR Compliant' },
          ].map((badge, index) => (
            <div
              key={index}
              className="flex items-center gap-2 rounded-lg border border-gray-800 bg-gray-900/50 px-4 py-2 backdrop-blur-sm"
            >
              <badge.icon className="h-4 w-4 text-purple-400" />
              <span className="text-sm text-gray-300">{badge.label}</span>
            </div>
          ))}
        </motion.div>
      </motion.div>

      {/* Scroll indicator */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1 }}
        className="absolute bottom-8 left-1/2 -translate-x-1/2"
      >
        <motion.div
          animate={{ y: [0, 10, 0] }}
          transition={{ duration: 2, repeat: Infinity }}
          className="h-6 w-4 rounded-full border-2 border-gray-600"
        >
          <motion.div
            animate={{ y: [0, 8, 0] }}
            transition={{ duration: 2, repeat: Infinity }}
            className="mx-auto mt-1 h-2 w-1 rounded-full bg-purple-500"
          />
        </motion.div>
      </motion.div>
    </section>
  );
};

// Stats Section with Silver Accents
const StatsSection = () => {
  const stats = [
    { value: '60%', label: 'Cost Reduction', icon: TrendingUp },
    { value: '75%', label: 'Faster Audits', icon: Zap },
    { value: '99.9%', label: 'Accuracy Rate', icon: CheckCircle },
    { value: '50+', label: 'Frameworks', icon: Globe },
  ];

  return (
    <section className="relative bg-gray-950 py-20">
      <div className="absolute inset-0 bg-gradient-to-b from-gray-950 via-purple-950/5 to-gray-950" />
      <div className="relative z-10 mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-2 gap-8 md:grid-cols-4">
          {stats.map((stat, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: index * 0.1 }}
              viewport={{ once: true }}
              className="group text-center"
            >
              <div className="relative mx-auto mb-4 flex h-16 w-16 items-center justify-center">
                <div className="absolute inset-0 rounded-full bg-gradient-to-r from-purple-600/20 to-purple-700/20 blur-xl transition-all group-hover:blur-2xl" />
                <div className="relative flex h-full w-full items-center justify-center rounded-full border border-purple-500/30 bg-gray-900/50 backdrop-blur-sm">
                  <stat.icon className="h-8 w-8 text-purple-400" />
                </div>
              </div>
              <div className="text-4xl font-bold bg-gradient-to-r from-white to-purple-200 bg-clip-text text-transparent">
                {stat.value}
              </div>
              <div className="mt-2 text-sm text-gray-400">{stat.label}</div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
};

// Features Section with Dark Cards
const FeaturesSection = () => {
  const features = [
    {
      icon: Zap,
      title: 'AI-Powered Analysis',
      description: 'Intelligent gap analysis and automated evidence collection powered by advanced AI',
      gradient: 'from-purple-600 to-purple-700',
    },
    {
      icon: BarChart3,
      title: 'Real-Time Monitoring',
      description: 'Continuous compliance tracking with instant alerts for any deviations',
      gradient: 'from-purple-700 to-purple-800',
    },
    {
      icon: FileCheck,
      title: 'Smart Reporting',
      description: 'Generate comprehensive compliance reports with a single click',
      gradient: 'from-purple-600 to-purple-700',
    },
    {
      icon: Users,
      title: 'Team Collaboration',
      description: 'Streamline workflows and enable seamless team coordination',
      gradient: 'from-purple-700 to-purple-800',
    },
    {
      icon: Shield,
      title: 'Policy Automation',
      description: 'Auto-generate and maintain policies aligned with your frameworks',
      gradient: 'from-purple-600 to-purple-700',
    },
    {
      icon: TrendingUp,
      title: 'Risk Assessment',
      description: 'Proactive risk identification and mitigation recommendations',
      gradient: 'from-purple-700 to-purple-800',
    },
  ];

  return (
    <section id="features" className="bg-black py-24">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="text-center">
          <h2 className="text-3xl font-bold text-white sm:text-4xl">
            Powerful Features
          </h2>
          <p className="mt-4 text-lg text-gray-400">
            Everything you need to automate compliance and reduce risk
          </p>
        </div>

        <div className="mt-16 grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((feature, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: index * 0.1 }}
              viewport={{ once: true }}
              className="group relative overflow-hidden rounded-2xl border border-gray-800 bg-gray-900/50 p-8 backdrop-blur-sm transition-all hover:border-purple-500/50"
            >
              {/* Gradient background on hover */}
              <div className="absolute inset-0 bg-gradient-to-br from-purple-600/5 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
              
              {/* Icon */}
              <div className="relative mb-6 inline-flex h-12 w-12 items-center justify-center rounded-lg bg-gradient-to-r from-purple-600/20 to-purple-700/20">
                <feature.icon className="h-6 w-6 text-purple-400" />
              </div>

              {/* Content */}
              <h3 className="mb-3 text-xl font-semibold text-white">
                {feature.title}
              </h3>
              <p className="text-gray-400">
                {feature.description}
              </p>

              {/* Silver accent line */}
              <div className="absolute bottom-0 left-0 h-1 w-0 bg-gradient-to-r from-purple-600 to-purple-400 transition-all group-hover:w-full" />
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
};

// Testimonials Section
const TestimonialsSection = () => {
  const testimonials = [
    {
      quote: "ruleIQ transformed our compliance process. What used to take weeks now takes days.",
      author: "Sarah Chen",
      role: "CISO",
      company: "TechFlow Solutions",
      rating: 5,
    },
    {
      quote: "The AI recommendations are spot-on. It's like having a compliance expert on call 24/7.",
      author: "Michael Rodriguez",
      role: "Compliance Officer",
      company: "HealthCare Plus",
      rating: 5,
    },
    {
      quote: "We saved over $200K in compliance costs within the first year. Incredible ROI.",
      author: "Jennifer Walsh",
      role: "VP Risk Management",
      company: "Global Finance Corp",
      rating: 5,
    },
  ];

  return (
    <section id="testimonials" className="bg-gray-950 py-24">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="text-center">
          <h2 className="text-3xl font-bold text-white sm:text-4xl">
            Loved by Teams
          </h2>
          <p className="mt-4 text-lg text-gray-400">
            See what compliance professionals are saying about ruleIQ
          </p>
        </div>

        <div className="mt-16 grid gap-8 md:grid-cols-3">
          {testimonials.map((testimonial, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: index * 0.1 }}
              viewport={{ once: true }}
              className="rounded-2xl border border-gray-800 bg-gray-900/50 p-6 backdrop-blur-sm"
            >
              {/* Stars */}
              <div className="mb-4 flex">
                {[...Array(testimonial.rating)].map((_, i) => (
                  <Star
                    key={i}
                    className="h-5 w-5 fill-purple-500 text-purple-500"
                  />
                ))}
              </div>

              {/* Quote */}
              <p className="mb-6 text-gray-300 italic">
                "{testimonial.quote}"
              </p>

              {/* Author */}
              <div className="border-t border-gray-800 pt-4">
                <p className="font-semibold text-white">{testimonial.author}</p>
                <p className="text-sm text-gray-400">{testimonial.role}</p>
                <p className="text-sm text-purple-400">{testimonial.company}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
};

// Pricing Section with Dark Cards
const PricingSection = () => {
  const plans = [
    {
      name: 'Starter',
      price: '£149',
      description: 'Perfect for small teams',
      features: [
        'Up to 2 frameworks',
        'Basic AI analysis',
        'Monthly reports',
        'Email support',
        '1 user account',
      ],
      popular: false,
    },
    {
      name: 'Professional',
      price: '£499',
      description: 'For growing companies',
      features: [
        'Unlimited frameworks',
        'Advanced AI features',
        'Real-time monitoring',
        'Priority support',
        '5 user accounts',
        'Custom policies',
        'API access',
      ],
      popular: true,
    },
    {
      name: 'Enterprise',
      price: 'Custom',
      description: 'For large organizations',
      features: [
        'Everything in Pro',
        'Unlimited users',
        'Dedicated support',
        'Custom integrations',
        'SLA guarantees',
        'On-premise option',
        'White-label',
      ],
      popular: false,
    },
  ];

  return (
    <section id="pricing" className="bg-black py-24">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="text-center">
          <h2 className="text-3xl font-bold text-white sm:text-4xl">
            Simple Pricing
          </h2>
          <p className="mt-4 text-lg text-gray-400">
            Choose the plan that fits your compliance needs
          </p>
        </div>

        <div className="mt-16 grid gap-8 lg:grid-cols-3">
          {plans.map((plan, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: index * 0.1 }}
              viewport={{ once: true }}
              className={cn(
                'relative rounded-2xl border p-8',
                plan.popular
                  ? 'border-purple-500 bg-gradient-to-b from-purple-950/30 to-gray-900/50'
                  : 'border-gray-800 bg-gray-900/50'
              )}
            >
              {plan.popular && (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                  <span className="rounded-full bg-gradient-to-r from-purple-600 to-purple-700 px-4 py-1 text-sm font-semibold text-white">
                    Most Popular
                  </span>
                </div>
              )}

              <div className="mb-8">
                <h3 className="text-2xl font-bold text-white">{plan.name}</h3>
                <div className="mt-4 flex items-baseline">
                  <span className="text-4xl font-bold text-white">
                    {plan.price}
                  </span>
                  {plan.price !== 'Custom' && (
                    <span className="ml-2 text-gray-400">/mo</span>
                  )}
                </div>
                <p className="mt-2 text-gray-400">{plan.description}</p>
              </div>

              <ul className="mb-8 space-y-3">
                {plan.features.map((feature, i) => (
                  <li key={i} className="flex items-center text-gray-300">
                    <CheckCircle className="mr-3 h-5 w-5 text-purple-400" />
                    {feature}
                  </li>
                ))}
              </ul>

              <Button
                className={cn(
                  'w-full',
                  plan.popular
                    ? 'bg-gradient-to-r from-purple-600 to-purple-700 text-white hover:from-purple-700 hover:to-purple-800'
                    : 'border border-gray-700 bg-gray-800/50 text-gray-300 hover:bg-gray-700/50 hover:text-white'
                )}
              >
                Get Started
              </Button>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
};

// CTA Section
const CTASection = () => {
  const router = useRouter();

  return (
    <section className="relative bg-gradient-to-r from-purple-900/20 via-purple-800/20 to-purple-900/20 py-24">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-purple-600/10 via-transparent to-transparent" />
      <div className="relative z-10 mx-auto max-w-4xl px-4 text-center sm:px-6 lg:px-8">
        <h2 className="text-3xl font-bold text-white sm:text-4xl">
          Ready to Transform Your Compliance?
        </h2>
        <p className="mt-4 text-lg text-gray-300">
          Join thousands of companies automating their compliance with AI
        </p>
        <Button
          size="lg"
          className="mt-8 bg-gradient-to-r from-purple-600 to-purple-700 px-8 py-6 text-base font-semibold text-white shadow-xl hover:from-purple-700 hover:to-purple-800"
          onClick={() => router.push('/signup')}
        >
          <span className="flex items-center">
            Start Free Assessment
            <ArrowRight className="ml-2 h-5 w-5" />
          </span>
        </Button>
      </div>
    </section>
  );
};

// Footer Section
const FooterSection = () => {
  return (
    <footer className="bg-gray-950 py-12 border-t border-gray-800">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid gap-8 md:grid-cols-4">
          <div>
            <h3 className="text-lg font-semibold text-white">ruleIQ</h3>
            <p className="mt-2 text-sm text-gray-400">
              AI-powered compliance automation for modern businesses
            </p>
          </div>
          <div>
            <h4 className="font-semibold text-white">Product</h4>
            <ul className="mt-4 space-y-2">
              <li>
                <Link href="/features" className="text-sm text-gray-400 hover:text-purple-400">
                  Features
                </Link>
              </li>
              <li>
                <Link href="/pricing" className="text-sm text-gray-400 hover:text-purple-400">
                  Pricing
                </Link>
              </li>
              <li>
                <Link href="/integrations" className="text-sm text-gray-400 hover:text-purple-400">
                  Integrations
                </Link>
              </li>
            </ul>
          </div>
          <div>
            <h4 className="font-semibold text-white">Company</h4>
            <ul className="mt-4 space-y-2">
              <li>
                <Link href="/about" className="text-sm text-gray-400 hover:text-purple-400">
                  About
                </Link>
              </li>
              <li>
                <Link href="/blog" className="text-sm text-gray-400 hover:text-purple-400">
                  Blog
                </Link>
              </li>
              <li>
                <Link href="/careers" className="text-sm text-gray-400 hover:text-purple-400">
                  Careers
                </Link>
              </li>
            </ul>
          </div>
          <div>
            <h4 className="font-semibold text-white">Support</h4>
            <ul className="mt-4 space-y-2">
              <li>
                <Link href="/help" className="text-sm text-gray-400 hover:text-purple-400">
                  Help Center
                </Link>
              </li>
              <li>
                <Link href="/contact" className="text-sm text-gray-400 hover:text-purple-400">
                  Contact
                </Link>
              </li>
              <li>
                <Link href="/status" className="text-sm text-gray-400 hover:text-purple-400">
                  Status
                </Link>
              </li>
            </ul>
          </div>
        </div>
        <div className="mt-8 border-t border-gray-800 pt-8 text-center">
          <p className="text-sm text-gray-400">
            © 2025 ruleIQ. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  );
};

// Main HomePage Component
export default function HomePage() {
  return (
    <div className="min-h-screen bg-black">
      <HeroSection />
      <StatsSection />
      <FeaturesSection />
      <TestimonialsSection />
      <PricingSection />
      <CTASection />
      <FooterSection />
    </div>
  );
}
