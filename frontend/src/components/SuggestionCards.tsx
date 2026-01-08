/**
 * SuggestionCards Component
 *
 * Elegant card-based UI for displaying renovation suggestions.
 * - Mobile: Vertically scrollable cards
 * - Desktop: Single card with side navigation arrows
 * - Details toggle inside each card
 * - Clean, lightweight design
 */

import { memo, useState, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Palette,
  Wrench,
  DollarSign,
  Clock,
  LinkIcon,
} from "lucide-react";

// ==================== TYPES ====================

export interface SuggestionOption {
  style_name: string;
  description: string;
  key_changes: string[];
  why_it_works?: string;
  budget_tier: "economy" | "mid-range" | "premium" | "mid" | "upper-mid";
  materials?: Record<string, string>;
  transformation_level?: "subtle" | "moderate" | "dramatic";
  estimated_cost_range?: string;
  timeline?: string;
}

export interface Source {
  title: string;
  url: string;
  snippet?: string;
}

interface SuggestionCardsProps {
  options: SuggestionOption[];
  sources?: Source[];
  onSelectOption: (optionIndex: number) => void;
}

// ==================== CONSTANTS ====================

const BUDGET_COLORS: Record<string, string> = {
  economy: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-400",
  "mid-range": "bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400",
  mid: "bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400",
  "upper-mid": "bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-400",
  premium: "bg-purple-100 text-purple-700 dark:bg-purple-500/20 dark:text-purple-400",
};

const TRANSFORMATION_ICONS: Record<string, string> = {
  subtle: "🌿",
  moderate: "✨",
  dramatic: "🔥",
};

// ==================== SINGLE CARD COMPONENT ====================

interface CardContentProps {
  option: SuggestionOption;
  index: number;
  totalCount: number;
  expanded: boolean;
  onToggleExpand: () => void;
  onSelect: () => void;
  sources: Source[];
  showSources: boolean;
}

const CardContent = memo(function CardContent({
  option,
  index,
  totalCount,
  expanded,
  onToggleExpand,
  onSelect,
  sources,
  showSources,
}: CardContentProps) {
  const budgetColor = BUDGET_COLORS[option.budget_tier] || BUDGET_COLORS["mid-range"];
  const transformationIcon = TRANSFORMATION_ICONS[option.transformation_level || "moderate"];

  // Filter out N/A materials
  const validMaterials = option.materials
    ? Object.entries(option.materials).filter(
        ([, value]) => value && value.toLowerCase() !== "n/a"
      )
    : [];

  return (
    <div className="bg-white dark:bg-navy-800 rounded-2xl border border-navy-200 dark:border-navy-700 overflow-hidden shadow-sm h-full flex flex-col">
      {/* Header */}
      <div className="p-4 sm:p-5 border-b border-navy-100 dark:border-navy-700">
        <div className="flex items-start justify-between gap-3 mb-2">
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <span className="text-xl sm:text-2xl flex-shrink-0">{transformationIcon}</span>
            <div className="flex-1 min-w-0">
              <h3 className="font-bold text-base sm:text-lg text-navy-900 dark:text-white truncate">
                {option.style_name}
              </h3>
              <span className="text-xs text-navy-400 dark:text-navy-500">
                Option {index + 1} of {totalCount}
              </span>
            </div>
          </div>
          <span className={`px-2 py-0.5 text-xs font-medium rounded-full flex-shrink-0 ${budgetColor}`}>
            {option.budget_tier}
          </span>
        </div>
        <p className="text-sm text-navy-600 dark:text-navy-300 leading-relaxed">
          {option.description}
        </p>
      </div>

      {/* Content */}
      <div className="p-4 sm:p-5 flex-1 overflow-y-auto">
        {/* Key Changes */}
        <div className="flex items-center gap-2 mb-3">
          <Wrench className="w-4 h-4 text-amber-500" />
          <span className="text-sm font-medium text-navy-700 dark:text-navy-300">
            Key Changes
          </span>
        </div>
        <ul className="space-y-2 mb-4">
          {option.key_changes.slice(0, expanded ? undefined : 3).map((change, i) => (
            <li
              key={i}
              className="flex items-start gap-2 text-sm text-navy-600 dark:text-navy-400"
            >
              <span className="text-amber-500 mt-0.5 flex-shrink-0">•</span>
              <span>{change}</span>
            </li>
          ))}
          {!expanded && option.key_changes.length > 3 && (
            <li className="text-xs text-navy-400 dark:text-navy-500 italic pl-4">
              +{option.key_changes.length - 3} more...
            </li>
          )}
        </ul>

        {/* Expanded Details */}
        <AnimatePresence>
          {expanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden"
            >
              {/* Materials */}
              {validMaterials.length > 0 && (
                <div className="mb-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Palette className="w-4 h-4 text-purple-500" />
                    <span className="text-sm font-medium text-navy-700 dark:text-navy-300">
                      Materials
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    {validMaterials.map(([key, value]) => (
                      <div
                        key={key}
                        className="bg-navy-50 dark:bg-navy-700/50 rounded-lg px-2.5 py-1.5"
                      >
                        <span className="text-navy-500 dark:text-navy-400 capitalize">
                          {key}:
                        </span>
                        <span className="ml-1 text-navy-700 dark:text-navy-300">{value}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Cost & Timeline */}
              {(option.estimated_cost_range || option.timeline) && (
                <div className="flex flex-wrap gap-4 mb-4">
                  {option.estimated_cost_range && (
                    <div className="flex items-center gap-1.5 text-sm text-navy-600 dark:text-navy-400">
                      <DollarSign className="w-4 h-4 text-emerald-500" />
                      <span>{option.estimated_cost_range}</span>
                    </div>
                  )}
                  {option.timeline && (
                    <div className="flex items-center gap-1.5 text-sm text-navy-600 dark:text-navy-400">
                      <Clock className="w-4 h-4 text-blue-500" />
                      <span>{option.timeline}</span>
                    </div>
                  )}
                </div>
              )}

              {/* Why it works */}
              {option.why_it_works && (
                <div className="p-3 bg-amber-50 dark:bg-amber-500/10 rounded-xl mb-4">
                  <p className="text-xs text-amber-800 dark:text-amber-300 leading-relaxed">
                    <span className="font-semibold">Why it works:</span> {option.why_it_works}
                  </p>
                </div>
              )}

              {/* Sources */}
              {showSources && sources.length > 0 && (
                <div className="pt-3 border-t border-navy-100 dark:border-navy-700">
                  <div className="flex items-center gap-2 mb-2">
                    <LinkIcon className="w-3.5 h-3.5 text-navy-400" />
                    <span className="text-xs font-medium text-navy-500 dark:text-navy-400">
                      Sources ({sources.length})
                    </span>
                  </div>
                  <div className="space-y-1">
                    {sources.slice(0, 4).map((source, i) => (
                      <a
                        key={i}
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1.5 text-xs text-navy-500 dark:text-navy-400 hover:text-amber-600 dark:hover:text-amber-400 transition-colors"
                      >
                        <ExternalLink className="w-3 h-3 flex-shrink-0" />
                        <span className="truncate">{source.title}</span>
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-navy-100 dark:border-navy-700 bg-navy-50/30 dark:bg-navy-900/30">
        <div className="flex gap-2">
          <button
            onClick={onToggleExpand}
            className="flex items-center justify-center gap-1.5 px-4 py-2.5 text-sm rounded-xl bg-white dark:bg-navy-800 border border-navy-200 dark:border-navy-600 text-navy-600 dark:text-navy-300 hover:bg-navy-50 dark:hover:bg-navy-700 transition-colors flex-shrink-0"
          >
            {expanded ? (
              <>
                <ChevronUp className="w-4 h-4" />
                Less
              </>
            ) : (
              <>
                <ChevronDown className="w-4 h-4" />
                Details
              </>
            )}
          </button>
          <motion.button
            onClick={onSelect}
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.99 }}
            className="flex-1 px-4 py-2.5 text-sm rounded-xl bg-gradient-to-r from-amber-500 to-amber-400 text-white font-medium shadow-sm hover:shadow-md transition-all"
          >
            Visualize This
          </motion.button>
        </div>
      </div>
    </div>
  );
});

// ==================== MAIN COMPONENT ====================

export function SuggestionCards({ options, sources = [], onSelectOption }: SuggestionCardsProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [expandedCards, setExpandedCards] = useState<Set<number>>(new Set());
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768);
    checkMobile();
    window.addEventListener("resize", checkMobile);
    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  const goToPrevious = useCallback(() => {
    setCurrentIndex((prev) => (prev > 0 ? prev - 1 : options.length - 1));
  }, [options.length]);

  const goToNext = useCallback(() => {
    setCurrentIndex((prev) => (prev < options.length - 1 ? prev + 1 : 0));
  }, [options.length]);

  const toggleExpanded = useCallback((index: number) => {
    setExpandedCards((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  }, []);

  // Empty state
  if (options.length === 0) {
    return (
      <div className="text-center py-8 text-navy-500 dark:text-navy-400">
        No suggestions available. Try describing what you're looking for!
      </div>
    );
  }

  // Single card with side navigation + swipe on mobile
  return (
    <div className="relative">
      {/* Navigation wrapper */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Left Arrow */}
        <motion.button
          onClick={goToPrevious}
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.95 }}
          className={`flex-shrink-0 flex items-center justify-center rounded-full bg-white dark:bg-navy-800 border border-navy-200 dark:border-navy-700 text-navy-500 dark:text-navy-400 hover:text-amber-500 hover:border-amber-300 dark:hover:border-amber-500 shadow-sm transition-all ${
            isMobile ? "w-8 h-8" : "w-10 h-10"
          }`}
        >
          <ChevronLeft className={isMobile ? "w-4 h-4" : "w-5 h-5"} />
        </motion.button>

        {/* Card with swipe support */}
        <motion.div
          className="flex-1 min-w-0 touch-pan-x"
          drag={isMobile ? "x" : false}
          dragConstraints={{ left: 0, right: 0 }}
          dragElastic={0.2}
          onDragEnd={(_, info) => {
            if (info.offset.x > 50) {
              goToPrevious();
            } else if (info.offset.x < -50) {
              goToNext();
            }
          }}
        >
          <AnimatePresence mode="wait">
            <motion.div
              key={currentIndex}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.2 }}
            >
              <CardContent
                option={options[currentIndex]}
                index={currentIndex}
                totalCount={options.length}
                expanded={expandedCards.has(currentIndex)}
                onToggleExpand={() => toggleExpanded(currentIndex)}
                onSelect={() => onSelectOption(currentIndex)}
                sources={sources}
                showSources={sources.length > 0}
              />
            </motion.div>
          </AnimatePresence>
        </motion.div>

        {/* Right Arrow */}
        <motion.button
          onClick={goToNext}
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.95 }}
          className={`flex-shrink-0 flex items-center justify-center rounded-full bg-white dark:bg-navy-800 border border-navy-200 dark:border-navy-700 text-navy-500 dark:text-navy-400 hover:text-amber-500 hover:border-amber-300 dark:hover:border-amber-500 shadow-sm transition-all ${
            isMobile ? "w-8 h-8" : "w-10 h-10"
          }`}
        >
          <ChevronRight className={isMobile ? "w-4 h-4" : "w-5 h-5"} />
        </motion.button>
      </div>

      {/* Dot indicators */}
      {options.length > 1 && (
        <div className="flex justify-center gap-1.5 mt-3 sm:mt-4">
          {options.map((_, idx) => (
            <button
              key={idx}
              onClick={() => setCurrentIndex(idx)}
              className={`h-1.5 rounded-full transition-all duration-200 ${
                idx === currentIndex
                  ? "bg-amber-500 w-5 sm:w-6"
                  : "bg-navy-300 dark:bg-navy-600 w-1.5 hover:bg-navy-400 dark:hover:bg-navy-500"
              }`}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default memo(SuggestionCards);
