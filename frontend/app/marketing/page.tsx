'use client';

import { motion } from 'framer-motion';
import { ShieldCheck, FileText, BrainCircuit, CheckCircle, BarChart, Users } from 'lucide-react';
import Image from 'next/image';

import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { TextEffect } from '@/components/ui/text-effect';
import { TypewriterEffect } from '@/components/ui/typewriter-effect';
import { InfiniteSlider } from '@/components/ui/infinite-slider';
import { SparklesBackground } from '@/components/ui/sparkles-background';
import { GradientBackground } from '@/components/ui/gradient-background';
import { AnimatedGrid } from '@/components/ui/animated-grid';
import { FloatingElements } from '@/components/ui/floating-elements';
import { ShimmerButton } from '@/components/magicui/shimmer-button';
import { EnhancedMetricCard } from '@/components/dashboard/enhanced-metric-card';
import { NumberTicker } from '@/components/magicui/number-ticker';


export default function MarketingPage() {
  const typewriterWords = [
    { text: 'For UK SMBs', className: 'text-teal-600' },
    { text: 'AI-Powered', className: 'text-teal-600' },
    { text: 'Stay Compliant', className: 'text-teal-600' },
  ];

  const clientLogos = [
    {
      quote: 'Trusted Partner',
      name: 'Client 1',
      title: 'UK Enterprise',
      img: '/placeholder.svg?width=150&height=40',
    },
    {
      quote: 'Trusted Partner',
      name: 'Client 2',
      title: 'UK Enterprise',
      img: '/placeholder.svg?width=150&height=40',
    },
    {
      quote: 'Trusted Partner',
      name: 'Client 3',
      title: 'UK Enterprise',
      img: '/placeholder.svg?width=150&height=40',
    },
    {
      quote: 'Trusted Partner',
      name: 'Client 4',
      title: 'UK Enterprise',
      img: '/placeholder.svg?width=150&height=40',
    },
    {
      quote: 'Trusted Partner',
      name: 'Client 5',
      title: 'UK Enterprise',
      img: '/placeholder.svg?width=150&height=40',
    },
  ];

  const features = [
    {
      icon: <BrainCircuit size={24} className="text-white" />,
      title: 'AI-Powered Assessments',
      description:
        'Leverage artificial intelligence to conduct comprehensive compliance assessments, identifying gaps and risks with unparalleled accuracy.',
    },
    {
      icon: <FileText size={24} className="text-white" />,
      title: 'Evidence Management',
      description:
        'A centralized, secure repository for all your compliance evidence. Link documents to controls and automate collection.',
    },
    {
      icon: <ShieldCheck size={24} className="text-white" />,
      title: 'Policy Generation',
      description:
        'Automatically generate, customize, and manage compliance policies based on industry standards and your specific business needs.',
    },
  ];

  const howItWorksItems = [
    {
      title: 'Connect Your Systems',
      description:
        'Integrate seamlessly with your existing tools and platforms. ruleIQ pulls data from your cloud services, code repositories, and HR systems.',
      icon: <Users size={20} className="text-white" />,
    },
    {
      title: 'AI Analyzes Compliance',
      description:
        'Our intelligent engine analyzes your data against hundreds of controls from various frameworks like ISO 27001, GDPR, and SOC 2.',
      icon: <BarChart size={20} className="text-white" />,
    },
    {
      title: 'Get Actionable Insights',
      description:
        'Receive a clear, prioritized list of actions. The dashboard visualizes your compliance posture, making it easy to track progress and report to stakeholders.',
      icon: <CheckCircle size={20} className="text-white" />,
    },
  ];

  const testimonials = [
    {
      quote:
        "ruleIQ transformed our compliance process from a quarterly headache to a continuous, automated workflow. We're more secure and saved hundreds of hours.",
      name: 'Jane Doe',
      title: 'CTO, TechCorp',
      img: '/placeholder.svg?width=80&height=80',
    },
    {
      quote:
        'The AI-powered insights are a game-changer. We identified critical risks we would have otherwise missed. Highly recommended for any growing business in the UK.',
      name: 'John Smith',
      title: 'CEO, Innovate Solutions',
      img: '/placeholder.svg?width=80&height=80',
    },
  ];

  return (
    <div className="relative min-h-screen overflow-x-hidden bg-background text-foreground">
      {/* Hero Section */}
      <section className="relative h-screen w-full overflow-hidden">
        {/* Clean background for optimal text readability */}
        <div className="absolute inset-0 bg-gradient-to-br from-white via-teal-50/10 to-white" />
        
        <div className="relative z-20 flex h-full flex-col items-center justify-center px-4">
          <div className="space-y-8 text-center">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, ease: "easeOut" }}
              className="text-sm font-semibold text-teal-600 uppercase tracking-widest mb-4"
            >
              AI-Powered Compliance Platform
            </motion.div>
            
            <TextEffect
              per="word"
              preset="fade-in-blur"
              className="text-5xl font-bold md:text-7xl lg:text-8xl leading-tight text-foreground"
            >
              Automate Compliance, Eliminate Risk
            </TextEffect>
            
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.3 }}
              className="text-xl md:text-2xl text-muted-foreground max-w-4xl mx-auto leading-relaxed"
            >
              Transform your compliance workflow with intelligent automation. 
              Built specifically for UK SMBs navigating ISO 27001, GDPR, and SOC 2.
            </motion.p>
            
            <TypewriterEffect words={typewriterWords} />
            <div className="relative flex items-center justify-center space-x-4">
              <ShimmerButton
                className="z-10 bg-teal-600 text-lg px-8 py-4 h-auto rounded-xl shadow-lg hover:shadow-xl transition-all duration-300 transform hover:-translate-y-1 group"
                shimmerColor="#4FD1C5"
                background="linear-gradient(135deg, #2C7A7B 0%, #319795 100%)"
              >
                <span className="flex items-center gap-2 text-white font-semibold">
                  Start Free Trial
                  <motion.span
                    className="group-hover:translate-x-1 transition-transform duration-200"
                    initial={{ x: 0 }}
                    animate={{ x: [0, 3, 0] }}
                    transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
                  >
                    →
                  </motion.span>
                </span>
              </ShimmerButton>
              <Button 
                variant="outline" 
                size="lg" 
                className="z-10 border-2 border-teal-600 text-teal-600 hover:bg-teal-50 hover:border-teal-700 text-lg px-8 py-4 h-auto rounded-xl transition-all duration-300"
              >
                Watch 2-min Demo
              </Button>
            </div>
            
            {/* Trust indicators */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.9 }}
              className="text-sm text-muted-foreground font-medium"
            >
              No credit card required • 14-day free trial • Setup in 5 minutes
            </motion.div>
          </div>
          <div className="absolute bottom-10 flex space-x-8">
            {['ISO 27001', 'GDPR', 'SOC 2'].map((badge, i) => (
              <motion.div
                key={badge}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: [0, -10, 0] }}
                transition={{
                  duration: 0.5,
                  delay: 1 + i * 0.2,
                  repeat: Infinity,
                  repeatType: 'mirror',
                  ease: 'easeInOut',
                }}
                className="flex items-center gap-2 rounded-full border border-teal-600/30 bg-teal-50/50 px-4 py-2 text-sm"
              >
                <CheckCircle className="h-4 w-4 text-green-500" />
                {badge}
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Social Proof Section */}
      <section className="py-20">
        <GradientBackground containerClassName="max-w-5xl mx-auto rounded-[22px]">
          <div className="p-8">
            <h3 className="mb-8 text-center text-2xl font-semibold">
              Trusted by 500+ UK businesses
            </h3>
            <InfiniteSlider items={clientLogos} direction="right" speed="slow" />
          </div>
        </GradientBackground>
      </section>

      {/* Metrics Section */}
      <section className="py-20 bg-gradient-to-r from-teal-50 to-white">
        <div className="container mx-auto px-4">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-neutral-900 mb-4">
              Trusted by Growing Businesses
            </h2>
            <p className="text-neutral-600 max-w-2xl mx-auto">
              Join hundreds of UK SMBs who have transformed their compliance operations with ruleIQ
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-8 max-w-4xl mx-auto">
            <EnhancedMetricCard
              title="Active Users"
              value={500}
              suffix="+"
              description="UK businesses trust ruleIQ"
              icon={<Users className="h-5 w-5" />}
              className="text-center"
            />
            <EnhancedMetricCard
              title="Compliance Score"
              value={98}
              suffix="%"
              description="Average improvement"
              icon={<BarChart className="h-5 w-5" />}
              change={{ value: 15, trend: 'up' }}
              className="text-center"
            />
            <EnhancedMetricCard
              title="Time Saved"
              value={75}
              suffix="%"
              description="Reduction in manual work"
              icon={<CheckCircle className="h-5 w-5" />}
              change={{ value: 25, trend: 'up' }}
              className="text-center"
            />
            <EnhancedMetricCard
              title="Frameworks"
              value={12}
              suffix="+"
              description="Supported standards"
              icon={<ShieldCheck className="h-5 w-5" />}
              className="text-center"
            />
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="px-4 py-20">
        <h2 className="mb-12 text-center text-4xl font-bold md:text-5xl">
          Everything you need. Nothing you don't.
        </h2>
        <div className="mx-auto grid max-w-6xl grid-cols-1 gap-8 md:grid-cols-3">
          {features.map((feature, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: i * 0.1 }}
              viewport={{ once: true }}
            >
              <Card className="p-6 text-center transition-shadow hover:shadow-lg bg-white border border-teal-100 hover:border-teal-300">
                <CardContent className="space-y-4">
                  <div className="mx-auto w-16 h-16 bg-teal-600 rounded-lg flex items-center justify-center mb-4">
                    {feature.icon}
                  </div>
                  <h3 className="text-xl font-bold">{feature.title}</h3>
                  <p className="text-muted-foreground">{feature.description}</p>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Product Demo Section */}
      <section className="py-20">
        <div className="container mx-auto px-4 text-center">
          <TextEffect per="word" preset="slide" className="mb-8 text-4xl font-semibold">
            Your Compliance Command Center
          </TextEffect>
          <TextEffect
            per="word"
            preset="scale"
            className="mb-12 text-4xl font-bold leading-none text-teal-600 md:text-[6rem]"
            delay={1000}
          >
            One Dashboard
          </TextEffect>
          <div className="relative">
            <Image
              src="/placeholder.svg?width=1200&height=800&query=modern+dark+theme+compliance+dashboard+UI"
              alt="Product demo"
              height={800}
              width={1200}
              className="mx-auto h-full rounded-2xl object-cover object-left-top shadow-2xl"
              draggable={false}
            />
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section id="how-it-works" className="py-20">
        <div className="container mx-auto px-4">
          <motion.h1
            initial={{ opacity: 0.5, y: 100 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{
              delay: 0.3,
              duration: 0.8,
              ease: 'easeInOut',
            }}
            className="mb-12 text-center text-4xl font-medium tracking-tight md:text-7xl"
          >
            Simple Steps to Full Compliance
          </motion.h1>
          <div className="mx-auto grid max-w-6xl gap-8 md:grid-cols-3">
            {howItWorksItems.map((item, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: i * 0.1 }}
                viewport={{ once: true }}
                className="text-center"
              >
                <Card className="p-6 transition-shadow hover:shadow-lg bg-white border border-teal-100 hover:border-teal-300">
                  <CardContent className="space-y-4">
                    <div className="w-12 h-12 bg-teal-600 rounded-lg flex items-center justify-center mb-4">
                      {item.icon}
                    </div>
                    <h3 className="text-xl font-bold">{item.title}</h3>
                    <p className="text-muted-foreground">{item.description}</p>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Testimonials Section */}
      <section id="testimonials" className="relative py-20 bg-gray-50">
        <div className="container mx-auto px-4">
          <div className="mb-12 text-center">
            <h2 className="mb-4 text-2xl font-bold md:text-4xl lg:text-7xl">
              Don't just take our word for it.
            </h2>
            <p className="text-base font-normal text-muted-foreground md:text-lg">
              Hear from leaders who transformed their compliance with ruleIQ.
            </p>
          </div>
          <div className="mx-auto grid max-w-4xl grid-cols-1 gap-8 md:grid-cols-2">
            {testimonials.map((t, i) => (
              <GradientBackground key={i} containerClassName="rounded-2xl">
                <div className="space-y-4 p-8">
                  <p className="text-lg">"{t.quote}"</p>
                  <div className="flex items-center gap-4">
                    <Image
                      src={t.img || '/placeholder.svg'}
                      alt={t.name}
                      width={40}
                      height={40}
                      className="rounded-full"
                    />
                    <div>
                      <p className="font-semibold">{t.name}</p>
                      <p className="text-sm text-muted-foreground">{t.title}</p>
                    </div>
                  </div>
                </div>
              </GradientBackground>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="bg-gradient-to-b from-background to-teal-50 py-20">
        <div className="mx-auto max-w-3xl px-4 text-center">
          <TextEffect
            per="word"
            preset="fade-in-blur"
            className="mb-4 text-4xl font-bold md:text-5xl"
          >
            Ready to Automate Your Compliance?
          </TextEffect>
          <p className="mb-8 mt-4 text-muted-foreground">
            Join hundreds of UK businesses securing their operations with ruleIQ. Get started today.
          </p>
          <div className="mx-auto max-w-md">
            <div className="flex flex-col gap-4 sm:flex-row">
              <Input
                type="email"
                placeholder="Enter your email"
                className="border-teal-300 bg-background/50 focus:border-teal-600 focus:ring-teal-600"
              />
              <ShimmerButton
                className="w-full sm:w-auto bg-teal-600 hover:bg-teal-700"
                shimmerColor="#4FD1C5"
                background="linear-gradient(135deg, #2C7A7B 0%, #319795 100%)"
              >
                <span className="text-white font-semibold">Get Started Free</span>
              </ShimmerButton>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">No credit card required.</p>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-muted/50 px-4 py-12">
        <div className="mx-auto grid max-w-6xl grid-cols-1 gap-8 md:grid-cols-4">
          <div className="space-y-4">
            <div className="text-xl font-bold">ruleIQ</div>
            <p className="text-sm text-muted-foreground">
              Automated compliance for the modern business.
            </p>
          </div>
          <div>
            <h4 className="mb-4 font-semibold">Product</h4>
            <ul className="space-y-2 text-sm">
              <li>
                <a href="#features" className="hover:text-teal-600">
                  Features
                </a>
              </li>
              <li>
                <a href="#pricing" className="hover:text-teal-600">
                  Pricing
                </a>
              </li>
              <li>
                <a href="#integrations" className="hover:text-teal-600">
                  Integrations
                </a>
              </li>
              <li>
                <a href="#demo" className="hover:text-teal-600">
                  Request a Demo
                </a>
              </li>
            </ul>
          </div>
          <div>
            <h4 className="mb-4 font-semibold">Company</h4>
            <ul className="space-y-2 text-sm">
              <li>
                <a href="#about" className="hover:text-teal-600">
                  About Us
                </a>
              </li>
              <li>
                <a href="#blog" className="hover:text-teal-600">
                  Blog
                </a>
              </li>
              <li>
                <a href="#careers" className="hover:text-teal-600">
                  Careers
                </a>
              </li>
              <li>
                <a href="#contact" className="hover:text-teal-600">
                  Contact
                </a>
              </li>
            </ul>
          </div>
          <div>
            <h4 className="mb-4 font-semibold">Legal</h4>
            <ul className="space-y-2 text-sm">
              <li>
                <a href="#privacy" className="hover:text-teal-600">
                  Privacy Policy
                </a>
              </li>
              <li>
                <a href="#terms" className="hover:text-teal-600">
                  Terms of Service
                </a>
              </li>
            </ul>
          </div>
        </div>
        <div className="mt-12 border-t border-border pt-8 text-center text-sm">
          <p>&copy; {new Date().getFullYear()} ruleIQ. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}