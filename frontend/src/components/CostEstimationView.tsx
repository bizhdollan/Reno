import { useState, useCallback, memo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Check, ChevronDown, ChevronUp, Sparkles, DollarSign, TrendingUp, Shield, Star, ArrowRight } from "lucide-react";

interface CategoryBreakdown {
  category: string;
  description: string;
  materials_cost: number;
  labor_cost: number;
  total: number;
}

interface CostTier {
  id: string;
  name: string;
  badge: string;
  description: string;
  total_cost: number;
  cogs: number;
  markup_percentage: number;
  markup_amount: number;
  included_items: string[];
  detailed_breakdown: CategoryBreakdown[];
}

interface CostEstimationViewProps {
  tiers: CostTier[];
  onSelectTier: (tierId: string) => void;
  selectedImageUrl?: string;
  projectTitle?: string;
  projectType?: string;
}

const formatCurrency = (amount: number) => {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
};

// Badge configurations
const BADGE_CONFIG: Record<string, { bg: string; text: string; icon: React.ReactNode }> = {
  "Budget-Friendly": {
    bg: "bg-emerald-500/10 border-emerald-500/30",
    text: "text-emerald-400",
    icon: <DollarSign className="w-3.5 h-3.5" />,
  },
  "Recommended": {
    bg: "bg-amber-500/10 border-amber-500/30",
    text: "text-amber-400",
    icon: <Star className="w-3.5 h-3.5" />,
  },
  "Premium": {
    bg: "bg-purple-500/10 border-purple-500/30",
    text: "text-purple-400",
    icon: <Shield className="w-3.5 h-3.5" />,
  },
};

// Individual Tier Card
const TierCard = memo(function TierCard({
  tier,
  isSelected,
  isExpanded,
  isRecommended,
  onSelect,
  onToggleExpand,
}: {
  tier: CostTier;
  isSelected: boolean;
  isExpanded: boolean;
  isRecommended: boolean;
  onSelect: () => void;
  onToggleExpand: () => void;
}) {
  const badgeConfig = BADGE_CONFIG[tier.badge] || BADGE_CONFIG["Budget-Friendly"];

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      className={`relative flex flex-col h-full rounded-2xl border-2 transition-all duration-300 overflow-hidden ${
        isSelected
          ? "border-amber-500 bg-gradient-to-b from-amber-500/10 to-transparent shadow-xl shadow-amber-500/20"
          : isRecommended
          ? "border-amber-500/50 bg-navy-800/80 hover:border-amber-500/70"
          : "border-navy-700 bg-navy-800/80 hover:border-navy-600"
      }`}
    >
      {/* Recommended Badge */}
      {isRecommended && (
        <div className="absolute -top-0.5 left-1/2 -translate-x-1/2 z-10">
          <div className="px-4 py-1 bg-gradient-to-r from-amber-500 to-amber-400 text-navy-900 text-xs font-bold rounded-b-lg shadow-lg">
            RECOMMENDED
          </div>
        </div>
      )}

      {/* Card Header */}
      <div className={`p-6 ${isRecommended ? "pt-8" : ""}`}>
        {/* Badge */}
        <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full border ${badgeConfig.bg} ${badgeConfig.text} text-xs font-medium mb-4`}>
          {badgeConfig.icon}
          {tier.badge}
        </div>

        {/* Tier Name & Price */}
        <h3 className="text-xl font-bold text-white mb-1">{tier.name}</h3>
        <div className="flex items-baseline gap-2 mb-4">
          <span className="text-4xl font-bold text-white">{formatCurrency(tier.total_cost)}</span>
          <span className="text-sm text-navy-400">total</span>
        </div>

        {/* Description */}
        <p className="text-sm text-navy-300 mb-6 leading-relaxed">{tier.description}</p>

        {/* Cost Breakdown Summary */}
        <div className="flex items-center gap-4 py-3 px-4 bg-navy-900/50 rounded-xl mb-6">
          <div className="flex-1">
            <div className="text-xs text-navy-400 mb-0.5">Base Cost</div>
            <div className="text-sm font-semibold text-white">{formatCurrency(tier.cogs)}</div>
          </div>
          <div className="w-px h-8 bg-navy-700" />
          <div className="flex-1">
            <div className="text-xs text-navy-400 mb-0.5">Markup</div>
            <div className="text-sm font-semibold text-white">{tier.markup_percentage}%</div>
          </div>
        </div>

        {/* Included Items */}
        <div className="space-y-2 mb-6">
          <div className="text-xs font-medium text-navy-400 uppercase tracking-wider">What's Included</div>
          <div className="space-y-1.5">
            {tier.included_items.slice(0, 4).map((item, idx) => (
              <div key={idx} className="flex items-center gap-2 text-sm">
                <div className="w-5 h-5 rounded-full bg-emerald-500/20 flex items-center justify-center flex-shrink-0">
                  <Check className="w-3 h-3 text-emerald-400" />
                </div>
                <span className="text-navy-200">{item}</span>
              </div>
            ))}
            {tier.included_items.length > 4 && (
              <div className="text-xs text-navy-400 pl-7">
                +{tier.included_items.length - 4} more items
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Card Footer */}
      <div className="mt-auto p-6 pt-0 space-y-3">
        {/* Select Button */}
        <motion.button
          onClick={onSelect}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          className={`w-full py-3.5 rounded-xl font-semibold text-sm transition-all flex items-center justify-center gap-2 ${
            isSelected
              ? "bg-amber-500 text-navy-900 shadow-lg shadow-amber-500/30"
              : isRecommended
              ? "bg-amber-500/20 text-amber-400 hover:bg-amber-500/30 border border-amber-500/50"
              : "bg-navy-700 text-white hover:bg-navy-600"
          }`}
        >
          {isSelected ? (
            <>
              <Check className="w-4 h-4" />
              Selected
            </>
          ) : (
            <>
              Select This Tier
              <ArrowRight className="w-4 h-4" />
            </>
          )}
        </motion.button>

        {/* View Details Button */}
        <button
          onClick={onToggleExpand}
          className="w-full py-2.5 text-sm text-navy-400 hover:text-navy-200 transition-colors flex items-center justify-center gap-1"
        >
          {isExpanded ? "Hide Details" : "View Detailed Breakdown"}
          {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>

      {/* Expanded Details */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="overflow-hidden border-t border-navy-700"
          >
            <div className="p-6 bg-navy-900/50">
              <h4 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-amber-400" />
                Cost Breakdown
              </h4>
              <div className="space-y-3">
                {tier.detailed_breakdown.map((item, idx) => (
                  <div key={idx} className="flex items-center justify-between py-2 border-b border-navy-700/50 last:border-0">
                    <div>
                      <div className="text-sm font-medium text-white">{item.category}</div>
                      <div className="text-xs text-navy-400">{item.description}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-semibold text-white">{formatCurrency(item.total)}</div>
                      <div className="text-xs text-navy-400">
                        M: {formatCurrency(item.materials_cost)} | L: {formatCurrency(item.labor_cost)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Summary */}
              <div className="mt-4 pt-4 border-t border-navy-700 space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-navy-400">Subtotal (COGS)</span>
                  <span className="text-white font-medium">{formatCurrency(tier.cogs)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-navy-400">Markup ({tier.markup_percentage}%)</span>
                  <span className="text-white font-medium">{formatCurrency(tier.markup_amount)}</span>
                </div>
                <div className="flex justify-between text-base pt-2 border-t border-navy-700">
                  <span className="text-amber-400 font-bold">Total</span>
                  <span className="text-amber-400 font-bold">{formatCurrency(tier.total_cost)}</span>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
});

// Main Component
export function CostEstimationView({
  tiers,
  onSelectTier,
  selectedImageUrl,
  projectTitle,
  projectType,
}: CostEstimationViewProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const handleConfirm = useCallback(() => {
    if (selectedId) {
      onSelectTier(selectedId);
    }
  }, [selectedId, onSelectTier]);

  const selectedTier = tiers.find((t) => t.id === selectedId);

  return (
    <div className="min-h-full bg-gradient-to-b from-navy-900 to-navy-950 p-6 lg:p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-10"
        >
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-amber-500/10 rounded-full text-amber-400 text-sm font-medium mb-4">
            <Sparkles className="w-4 h-4" />
            Your Estimate is Ready
          </div>
          <h1 className="text-3xl lg:text-4xl font-bold text-white mb-3">
            {projectTitle ? `${projectTitle} - ` : ""}Choose Your Renovation Tier
          </h1>
          <p className="text-navy-300 max-w-2xl mx-auto">
            Based on your {projectType || "renovation"} design, here are three pricing options.
            Select the tier that best fits your budget and preferences.
          </p>
        </motion.div>

        {/* Preview Image (if available) */}
        {selectedImageUrl && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="mb-10 flex justify-center"
          >
            <div className="relative">
              <img
                src={selectedImageUrl}
                alt="Your Design"
                className="max-h-64 rounded-2xl shadow-2xl border border-navy-700"
              />
              <div className="absolute -bottom-3 left-1/2 -translate-x-1/2 px-4 py-1.5 bg-navy-800 border border-navy-700 rounded-full text-xs text-navy-300 whitespace-nowrap">
                Your Selected Design
              </div>
            </div>
          </motion.div>
        )}

        {/* Tier Cards Grid */}
        <div className="grid gap-6 lg:grid-cols-3 mb-8">
          {tiers.map((tier) => (
            <TierCard
              key={tier.id}
              tier={tier}
              isSelected={selectedId === tier.id}
              isExpanded={expandedId === tier.id}
              isRecommended={tier.badge === "Recommended"}
              onSelect={() => setSelectedId(tier.id)}
              onToggleExpand={() => setExpandedId(expandedId === tier.id ? null : tier.id)}
            />
          ))}
        </div>

        {/* Confirm Selection */}
        <AnimatePresence>
          {selectedId && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 20 }}
              className="flex flex-col items-center gap-4"
            >
              <div className="text-center">
                <div className="text-sm text-navy-400 mb-1">You selected</div>
                <div className="text-xl font-bold text-white">
                  {selectedTier?.name} - {selectedTier && formatCurrency(selectedTier.total_cost)}
                </div>
              </div>
              <motion.button
                onClick={handleConfirm}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="px-10 py-4 bg-gradient-to-r from-amber-500 to-amber-400 text-navy-900 font-bold rounded-xl shadow-xl shadow-amber-500/30 hover:shadow-2xl hover:shadow-amber-500/40 transition-all flex items-center gap-2 text-lg"
              >
                Confirm Selection
                <ArrowRight className="w-5 h-5" />
              </motion.button>
              <p className="text-xs text-navy-400">
                You can save or share your estimate after confirmation
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

export default CostEstimationView;
