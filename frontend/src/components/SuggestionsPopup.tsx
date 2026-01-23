/**
 * SuggestionsPopup Component
 *
 * Modal popup to display pre-generated renovation suggestions.
 * - Shows when user clicks "Ideas Ready" button
 * - Displays suggestions in a carousel/card format
 * - User can select an option to visualize
 * - Responsive for mobile and desktop
 */

import { memo, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  Palette,
  DollarSign,
  Clock,
} from "lucide-react";
import { SuggestionOption, Source } from "./SuggestionCards";

interface SuggestionsPopupProps {
  isOpen: boolean;
  onClose: () => void;
  options: SuggestionOption[];
  sources?: Source[];
  onSelectOption: (optionIndex: number) => void;
}

const BUDGET_COLORS: Record<string, string> = {
  economy: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-400",
  "mid-range": "bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400",
  mid: "bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400",
  "upper-mid": "bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-400",
  premium: "bg-purple-100 text-purple-700 dark:bg-purple-500/20 dark:text-purple-400",
};

const TRANSFORMATION_ICONS: Record<string, string> = {
  subtle: "Fresh Touch",
  moderate: "Style Refresh",
  dramatic: "Full Transform",
};

function SuggestionsPopupComponent({
  isOpen,
  onClose,
  options,
  sources = [],
  onSelectOption,
}: SuggestionsPopupProps) {
  const [currentIndex, setCurrentIndex] = useState(0);

  const handlePrev = useCallback(() => {
    setCurrentIndex((prev) => (prev > 0 ? prev - 1 : options.length - 1));
  }, [options.length]);

  const handleNext = useCallback(() => {
    setCurrentIndex((prev) => (prev < options.length - 1 ? prev + 1 : 0));
  }, [options.length]);

  const handleSelect = useCallback(
    (index: number) => {
      onSelectOption(index);
      onClose();
    },
    [onSelectOption, onClose]
  );

  if (!options || options.length === 0) {
    return null;
  }

  const currentOption = options[currentIndex];

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          onClick={onClose}
        >
          {/* Backdrop */}
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

          {/* Popup Content */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
            transition={{ type: "spring", damping: 25, stiffness: 300 }}
            onClick={(e) => e.stopPropagation()}
            className="relative w-full max-w-lg max-h-[85vh] bg-white dark:bg-navy-800 rounded-2xl shadow-2xl overflow-hidden"
          >
            {/* Header */}
            <div className="sticky top-0 z-10 flex items-center justify-between px-4 py-3 border-b border-navy-100 dark:border-navy-700 bg-white dark:bg-navy-800">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-amber-500" />
                <h2 className="text-lg font-semibold text-navy-900 dark:text-white">
                  Renovation Ideas
                </h2>
              </div>
              <button
                onClick={onClose}
                className="p-2 rounded-full hover:bg-navy-100 dark:hover:bg-navy-700 transition-colors"
              >
                <X className="w-5 h-5 text-navy-500" />
              </button>
            </div>

            {/* Card Navigation */}
            <div className="relative">
              {/* Navigation Arrows */}
              {options.length > 1 && (
                <>
                  <button
                    onClick={handlePrev}
                    className="absolute left-2 top-1/2 -translate-y-1/2 z-10 p-2 rounded-full bg-white/90 dark:bg-navy-700/90 shadow-lg hover:bg-white dark:hover:bg-navy-600 transition-colors"
                  >
                    <ChevronLeft className="w-5 h-5 text-navy-600 dark:text-navy-300" />
                  </button>
                  <button
                    onClick={handleNext}
                    className="absolute right-2 top-1/2 -translate-y-1/2 z-10 p-2 rounded-full bg-white/90 dark:bg-navy-700/90 shadow-lg hover:bg-white dark:hover:bg-navy-600 transition-colors"
                  >
                    <ChevronRight className="w-5 h-5 text-navy-600 dark:text-navy-300" />
                  </button>
                </>
              )}

              {/* Card Content */}
              <div className="p-4 overflow-y-auto max-h-[60vh]">
                <AnimatePresence mode="wait">
                  <motion.div
                    key={currentIndex}
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -20 }}
                    transition={{ duration: 0.2 }}
                  >
                    {/* Style Name & Badge */}
                    <div className="flex items-start justify-between gap-2 mb-3">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-lg">
                            {currentOption.transformation_level
                              ? TRANSFORMATION_ICONS[currentOption.transformation_level] || ""
                              : ""}
                          </span>
                          <h3 className="text-xl font-bold text-navy-900 dark:text-white">
                            {currentOption.style_name}
                          </h3>
                        </div>
                        <p className="text-sm text-navy-500 dark:text-navy-400">
                          Option {currentIndex + 1} of {options.length}
                        </p>
                      </div>
                      <span
                        className={`px-2 py-1 text-xs font-medium rounded-full ${
                          BUDGET_COLORS[currentOption.budget_tier] || BUDGET_COLORS["mid-range"]
                        }`}
                      >
                        {currentOption.budget_tier}
                      </span>
                    </div>

                    {/* Description */}
                    <p className="text-navy-700 dark:text-navy-300 mb-4">
                      {currentOption.description}
                    </p>

                    {/* Key Changes */}
                    <div className="mb-4">
                      <div className="flex items-center gap-2 mb-2">
                        <Palette className="w-4 h-4 text-amber-500" />
                        <span className="text-sm font-medium text-navy-900 dark:text-white">
                          Key Changes
                        </span>
                      </div>
                      <ul className="space-y-1.5">
                        {currentOption.key_changes.slice(0, 5).map((change, i) => (
                          <li
                            key={i}
                            className="flex items-start gap-2 text-sm text-navy-600 dark:text-navy-400"
                          >
                            <span className="w-1.5 h-1.5 rounded-full bg-amber-500 mt-1.5 flex-shrink-0" />
                            {change}
                          </li>
                        ))}
                      </ul>
                    </div>

                    {/* Cost & Timeline */}
                    <div className="flex flex-wrap gap-3 mb-4">
                      {currentOption.estimated_cost_range && (
                        <div className="flex items-center gap-1.5 text-sm text-navy-600 dark:text-navy-400">
                          <DollarSign className="w-4 h-4 text-emerald-500" />
                          <span>{currentOption.estimated_cost_range}</span>
                        </div>
                      )}
                      {currentOption.timeline && (
                        <div className="flex items-center gap-1.5 text-sm text-navy-600 dark:text-navy-400">
                          <Clock className="w-4 h-4 text-blue-500" />
                          <span>{currentOption.timeline}</span>
                        </div>
                      )}
                    </div>

                    {/* Materials */}
                    {currentOption.materials &&
                      Object.keys(currentOption.materials).length > 0 && (
                        <div className="mb-4 p-3 bg-navy-50 dark:bg-navy-900/50 rounded-lg">
                          <span className="text-xs font-medium text-navy-500 dark:text-navy-400 uppercase tracking-wide">
                            Materials
                          </span>
                          <div className="mt-2 grid grid-cols-2 gap-2">
                            {Object.entries(currentOption.materials)
                              .slice(0, 6)
                              .map(([key, value]) => (
                                <div key={key} className="text-sm">
                                  <span className="text-navy-500 dark:text-navy-400 capitalize">
                                    {key}:
                                  </span>{" "}
                                  <span className="text-navy-700 dark:text-navy-300">
                                    {value}
                                  </span>
                                </div>
                              ))}
                          </div>
                        </div>
                      )}
                  </motion.div>
                </AnimatePresence>
              </div>
            </div>

            {/* Footer - Visualize Button */}
            <div className="sticky bottom-0 p-4 border-t border-navy-100 dark:border-navy-700 bg-white dark:bg-navy-800">
              <motion.button
                onClick={() => handleSelect(currentIndex)}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="w-full py-3 px-4 bg-gradient-to-r from-amber-500 to-amber-400 text-white font-semibold rounded-xl shadow-lg shadow-amber-500/25 hover:shadow-xl hover:shadow-amber-500/30 transition-all"
              >
                Visualize This Style
              </motion.button>

              {/* Dots Indicator */}
              {options.length > 1 && (
                <div className="flex justify-center gap-1.5 mt-3">
                  {options.map((_, i) => (
                    <button
                      key={i}
                      onClick={() => setCurrentIndex(i)}
                      className={`w-2 h-2 rounded-full transition-colors ${
                        i === currentIndex
                          ? "bg-amber-500"
                          : "bg-navy-200 dark:bg-navy-600 hover:bg-navy-300 dark:hover:bg-navy-500"
                      }`}
                    />
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export const SuggestionsPopup = memo(SuggestionsPopupComponent);
export default SuggestionsPopup;
