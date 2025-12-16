import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { 
  ArrowRight, 
  Sparkles, 
  Camera, 
  Brain, 
  DollarSign,
  CheckCircle2,
  Users,
  Clock,
  Shield
} from 'lucide-react';

// Animation variants
const fadeInUp = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 }
};

const staggerContainer = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1
    }
  }
};

const scaleIn = {
  hidden: { opacity: 0, scale: 0.8 },
  visible: { opacity: 1, scale: 1 }
};

// Floating shapes for background
function FloatingShapes() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      <motion.div
        animate={{ 
          y: [0, -20, 0],
          rotate: [0, 5, 0]
        }}
        transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
        className="absolute top-20 left-[10%] w-64 h-64 bg-amber-500/10 rounded-full blur-3xl"
      />
      <motion.div
        animate={{ 
          y: [0, 20, 0],
          rotate: [0, -5, 0]
        }}
        transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
        className="absolute top-40 right-[15%] w-96 h-96 bg-blue-500/10 rounded-full blur-3xl"
      />
      <motion.div
        animate={{ 
          y: [0, 15, 0],
          x: [0, 10, 0]
        }}
        transition={{ duration: 7, repeat: Infinity, ease: "easeInOut" }}
        className="absolute bottom-20 left-[20%] w-72 h-72 bg-purple-500/10 rounded-full blur-3xl"
      />
    </div>
  );
}

// Grid pattern overlay
function GridPattern() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none opacity-[0.015] dark:opacity-[0.03]">
      <div 
        className="absolute inset-0"
        style={{
          backgroundImage: `linear-gradient(#1E3A5F 1px, transparent 1px), linear-gradient(90deg, #1E3A5F 1px, transparent 1px)`,
          backgroundSize: '60px 60px'
        }}
      />
    </div>
  );
}

// Step card for How It Works
interface StepCardProps {
  number: number;
  icon: React.ReactNode;
  title: string;
  description: string;
}

function StepCard({ number, icon, title, description }: StepCardProps) {
  return (
    <motion.div
      variants={fadeInUp}
      whileHover={{ y: -5, transition: { duration: 0.2 } }}
      className="relative group"
    >
      <div className="absolute inset-0 bg-gradient-to-br from-amber-500/20 to-transparent rounded-2xl blur-xl opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
      <div className="relative bg-white dark:bg-navy-800 rounded-2xl p-6 border border-navy-100 dark:border-navy-700 shadow-sm hover:shadow-xl transition-all duration-300">
        {/* Step number */}
        <div className="absolute -top-3 -left-3 w-8 h-8 bg-amber-500 rounded-full flex items-center justify-center text-white font-bold text-sm shadow-lg">
          {number}
        </div>
        
        {/* Icon */}
        <div className="w-14 h-14 bg-gradient-to-br from-navy-100 to-navy-50 dark:from-navy-700 dark:to-navy-800 rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform duration-300">
          {icon}
        </div>
        
        <h3 className="text-lg font-semibold text-navy-900 dark:text-white mb-2">{title}</h3>
        <p className="text-navy-600 dark:text-navy-300 text-sm leading-relaxed">{description}</p>
      </div>
    </motion.div>
  );
}

// Feature badge
interface FeatureBadgeProps {
  icon: React.ReactNode;
  text: string;
}

function FeatureBadge({ icon, text }: FeatureBadgeProps) {
  return (
    <motion.div 
      variants={scaleIn}
      className="flex items-center gap-2 px-4 py-2 bg-white/80 dark:bg-navy-800/80 backdrop-blur-sm rounded-full border border-navy-100 dark:border-navy-700 shadow-sm"
    >
      <span className="text-emerald-500">{icon}</span>
      <span className="text-sm text-navy-700 dark:text-navy-200">{text}</span>
    </motion.div>
  );
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-navy-50 via-white to-navy-50 dark:from-navy-950 dark:via-navy-900 dark:to-navy-950">
      {/* Hero Section */}
      <section className="relative min-h-screen flex items-center justify-center overflow-hidden">
        <FloatingShapes />
        <GridPattern />
        
        {/* Hero gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-b from-navy-900/95 via-navy-900/80 to-navy-900/95 dark:from-navy-950/95 dark:via-navy-950/80 dark:to-navy-950/95" />
        
        <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-24 pb-16">
          <motion.div
            initial="hidden"
            animate="visible"
            variants={staggerContainer}
            className="text-center"
          >
            {/* Badge */}
            <motion.div
              variants={fadeInUp}
              className="inline-flex items-center gap-2 px-4 py-2 bg-white/10 backdrop-blur-sm rounded-full border border-white/20 mb-8"
            >
              <Sparkles className="w-4 h-4 text-amber-400" />
              <span className="text-sm text-white/90">AI-Powered Renovation Estimates</span>
            </motion.div>

            {/* Main heading */}
            <motion.h1
              variants={fadeInUp}
              className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-bold text-white mb-6 leading-tight"
            >
              Know Your Renovation Cost
              <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-amber-400 to-amber-500">
                Before You Commit
              </span>
            </motion.h1>

            {/* Subtitle */}
            <motion.p
              variants={fadeInUp}
              className="text-lg sm:text-xl text-navy-200 max-w-2xl mx-auto mb-10"
            >
              Get instant, professional 3-tier estimates powered by AI. 
              No more guessing, no more waiting—just transparent pricing in seconds.
            </motion.p>

            {/* CTA Buttons */}
            <motion.div
              variants={fadeInUp}
              className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-12"
            >
              <Link to="/estimate">
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  className="group flex items-center gap-2 px-8 py-4 bg-gradient-to-r from-amber-500 to-amber-400 text-navy-900 font-semibold rounded-xl shadow-lg shadow-amber-500/25 hover:shadow-xl hover:shadow-amber-500/30 transition-all duration-300"
                >
                  <span>Get Free Estimate</span>
                  <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                </motion.button>
              </Link>
              
              <Link to="/marketplace">
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  className="flex items-center gap-2 px-8 py-4 bg-white/10 backdrop-blur-sm text-white font-semibold rounded-xl border border-white/20 hover:bg-white/20 transition-all duration-300"
                >
                  <Users className="w-5 h-5" />
                  <span>I'm a Contractor</span>
                </motion.button>
              </Link>
            </motion.div>

            {/* Feature badges */}
            <motion.div
              variants={staggerContainer}
              initial="hidden"
              animate="visible"
              className="flex flex-wrap items-center justify-center gap-3"
            >
              <FeatureBadge icon={<CheckCircle2 className="w-4 h-4" />} text="No signup required" />
              <FeatureBadge icon={<Clock className="w-4 h-4" />} text="Results in 60 seconds" />
              <FeatureBadge icon={<Shield className="w-4 h-4" />} text="100% free for homeowners" />
            </motion.div>
          </motion.div>
        </div>

        {/* Scroll indicator */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1 }}
          className="absolute bottom-8 left-1/2 -translate-x-1/2"
        >
          <motion.div
            animate={{ y: [0, 8, 0] }}
            transition={{ duration: 1.5, repeat: Infinity }}
            className="w-6 h-10 border-2 border-white/30 rounded-full flex items-start justify-center p-2"
          >
            <div className="w-1.5 h-1.5 bg-white/60 rounded-full" />
          </motion.div>
        </motion.div>
      </section>

      {/* How It Works Section */}
      <section className="relative py-24 overflow-hidden">
        <GridPattern />
        
        <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-100px" }}
            variants={staggerContainer}
            className="text-center mb-16"
          >
            <motion.span
              variants={fadeInUp}
              className="inline-block px-4 py-1 bg-amber-100 dark:bg-amber-500/20 text-amber-600 dark:text-amber-400 text-sm font-medium rounded-full mb-4"
            >
              Simple Process
            </motion.span>
            <motion.h2
              variants={fadeInUp}
              className="text-3xl sm:text-4xl font-bold text-navy-900 dark:text-white mb-4"
            >
              How It Works
            </motion.h2>
            <motion.p
              variants={fadeInUp}
              className="text-navy-600 dark:text-navy-300 max-w-2xl mx-auto"
            >
              Get your renovation estimate in three simple steps
            </motion.p>
          </motion.div>

          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-100px" }}
            variants={staggerContainer}
            className="grid md:grid-cols-3 gap-8"
          >
            <StepCard
              number={1}
              icon={<Camera className="w-7 h-7 text-navy-600 dark:text-navy-300" />}
              title="Upload Photos"
              description="Take a few photos of your space with your phone. Our AI analyzes materials, dimensions, and current condition."
            />
            <StepCard
              number={2}
              icon={<Brain className="w-7 h-7 text-navy-600 dark:text-navy-300" />}
              title="AI Analysis"
              description="Our AI extracts details, confirms with you, and understands your renovation vision and preferences."
            />
            <StepCard
              number={3}
              icon={<DollarSign className="w-7 h-7 text-navy-600 dark:text-navy-300" />}
              title="Get 3-Tier Estimate"
              description="Receive detailed cost breakdowns in Low, Mid, and High tiers. Choose what fits your budget."
            />
          </motion.div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-16 bg-gradient-to-r from-navy-900 to-navy-800 dark:from-navy-950 dark:to-navy-900">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={staggerContainer}
            className="grid grid-cols-2 md:grid-cols-4 gap-8"
          >
            {[
              { value: '500+', label: 'Estimates Generated' },
              { value: '$2M+', label: 'In Project Value' },
              { value: '98%', label: 'Accuracy Rate' },
              { value: '< 60s', label: 'Average Time' },
            ].map((stat, index) => (
              <motion.div
                key={index}
                variants={fadeInUp}
                className="text-center"
              >
                <div className="text-3xl sm:text-4xl font-bold text-white mb-2">{stat.value}</div>
                <div className="text-navy-300 text-sm">{stat.label}</div>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-24">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={staggerContainer}
            className="relative bg-gradient-to-br from-navy-900 to-navy-800 dark:from-navy-800 dark:to-navy-900 rounded-3xl p-8 sm:p-12 overflow-hidden"
          >
            {/* Background decoration */}
            <div className="absolute top-0 right-0 w-64 h-64 bg-amber-500/20 rounded-full blur-3xl" />
            <div className="absolute bottom-0 left-0 w-48 h-48 bg-blue-500/20 rounded-full blur-3xl" />
            
            <div className="relative z-10 text-center">
              <motion.h2
                variants={fadeInUp}
                className="text-2xl sm:text-3xl font-bold text-white mb-4"
              >
                Ready to Start Your Renovation?
              </motion.h2>
              <motion.p
                variants={fadeInUp}
                className="text-navy-200 mb-8 max-w-lg mx-auto"
              >
                Get your free estimate now. No credit card required, no obligations.
              </motion.p>
              <motion.div variants={fadeInUp}>
                <Link to="/estimate">
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    className="group inline-flex items-center gap-2 px-8 py-4 bg-gradient-to-r from-amber-500 to-amber-400 text-navy-900 font-semibold rounded-xl shadow-lg shadow-amber-500/25"
                  >
                    <span>Get Started Free</span>
                    <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                  </motion.button>
                </Link>
              </motion.div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 border-t border-navy-100 dark:border-navy-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-gradient-to-br from-amber-400 to-amber-500 rounded-lg flex items-center justify-center">
                <span className="text-white text-sm">🏠</span>
              </div>
              <span className="text-navy-900 dark:text-white font-semibold">RenovationTech</span>
            </div>
            <p className="text-sm text-navy-500 dark:text-navy-400">
              © 2024 RenovationTech. All rights reserved.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}