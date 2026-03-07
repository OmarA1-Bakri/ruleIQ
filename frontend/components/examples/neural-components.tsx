// Example Component Implementations - Neural Purple Theme
import Link from 'next/link';

// ============================================
// 1. Dashboard Page Example
// ============================================

export function DashboardPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-neural-purple-900 via-black to-black">
      {/* Header */}
      <header className="glass-dark border-b border-white/5 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <h1 className="text-2xl font-extralight tracking-tight text-white">
            Dashboard
          </h1>
          <div className="flex items-center gap-4">
            <span className="text-sm text-white/60 font-light">
              Last updated: 2 mins ago
            </span>
            <button className="btn-ghost">
              Refresh
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Metrics Grid */}
        <div className="grid-metrics mb-8">
          <MetricCard
            label="Total Policies"
            value="1,234"
            change="+12%"
            trend="up"
          />
          <MetricCard
            label="Compliance Rate"
            value="99.9%"
            change="+0.3%"
            trend="up"
          />
          <MetricCard
            label="Active Audits"
            value="56"
            change="-5%"
            trend="down"
          />
          <MetricCard
            label="Risk Score"
            value="Low"
            change="Stable"
            trend="stable"
          />
        </div>
      </main>
    </div>
  );
}
// ============================================
// 2. Metric Card Component
// ============================================

interface MetricCardProps {
  label: string;
  value: string;
  change: string;
  trend: 'up' | 'down' | 'stable';
}

export function MetricCard({ label, value, change, trend }: MetricCardProps) {
  return (
    <div className="metric-card group">
      <div className="flex items-start justify-between">
        <div>
          <p className="metric-label">{label}</p>
          <p className="metric-value">
            {value}
            {trend === 'up' && (
              <span className="text-neural-purple-400 ml-1">↑</span>
            )}
            {trend === 'down' && (
              <span className="text-error ml-1">↓</span>
            )}
          </p>
        </div>
      </div>
      <p className={`metric-change ${
        trend === 'up' ? 'metric-change-positive' : 
        trend === 'down' ? 'metric-change-negative' : 
        'text-white/40'
      }`}>
        {change} from last period
      </p>
    </div>
  );
}
// ============================================
// 3. Feature Card Component
// ============================================

interface FeatureCardProps {
  title: string;
  description: string;
  icon?: React.ReactNode;
}

export function FeatureCard({ title, description, icon }: FeatureCardProps) {
  return (
    <div className="card group cursor-pointer">
      {icon && (
        <div className="w-12 h-12 rounded-2xl bg-neural-purple-500/10 
                        flex items-center justify-center mb-6
                        group-hover:bg-neural-purple-500/20 transition-colors">
          {icon}
        </div>
      )}
      <h3 className="text-xl font-light text-white mb-3">
        {title}
      </h3>
      <p className="text-sm font-light text-white/60 leading-relaxed">
        {description}
      </p>
      <div className="mt-6 text-neural-purple-400 text-sm font-light
                      opacity-0 group-hover:opacity-100 transition-opacity">
        Learn more →
      </div>
    </div>
  );
}
// ============================================
// 4. Navigation Component
// ============================================

export function Navigation() {
  const links = [
    { href: '/', label: 'Home' },
    { href: '/features', label: 'Features' },
    { href: '/pricing', label: 'Pricing' },
    { href: '/about', label: 'About' },
  ];

  return (
    <nav className="glass-dark border-b border-white/5">
      <div className="max-w-7xl mx-auto px-6">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <div className="flex items-center gap-8">
            <Link href="/" className="flex items-center gap-2">
              <span className="text-2xl font-extralight text-white">
                Rule<span className="text-neural-purple-400">IQ</span>
              </span>
            </Link>

            {/* Nav Links */}
            <div className="hidden md:flex items-center gap-6">
              {links.map((link) => (
                <a
                  key={link.href}
                  href={link.href}
                  className="nav-link"
                >
                  {link.label}
                </a>
              ))}
            </div>
          </div>

          {/* Right Side */}
          <div className="flex items-center gap-4">
            <button className="btn-ghost">
              Sign In
            </button>
            <button className="btn-primary">
              Get Started
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
}