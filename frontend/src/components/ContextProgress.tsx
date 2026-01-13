/**
 * ContextProgress Component
 *
 * Looping progress indicator that shows analysis steps during image upload.
 * Sticky at the bottom near input, loops until response arrives.
 */

import { memo, useEffect, useState, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Camera,
  Search,
  Loader2,
} from "lucide-react";

// ==================== TYPES ====================

interface ProgressStep {
  id: string;
  label: string;
}

// All possible steps/queries to cycle through
const ANALYSIS_STEPS: ProgressStep[] = [
  { id: "load", label: "Loading images" },
  { id: "extract", label: "Extracting room details" },
  { id: "context", label: "Building search context" },
];

const SEARCH_QUERIES: string[] = [
  "Finding local contractors",
  "Searching design trends",
  "Gathering material costs",
  "Analyzing room layouts",
];

// ==================== MAIN COMPONENT ====================

export function ContextProgress() {
  const [phase, setPhase] = useState<"analysis" | "search">("analysis");
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [currentQueryIndex, setCurrentQueryIndex] = useState(0);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  // Looping animation - cycles through steps/queries
  useEffect(() => {
    const cycleProgress = () => {
      if (phase === "analysis") {
        setCurrentStepIndex((prev) => {
          const next = prev + 1;
          if (next >= ANALYSIS_STEPS.length) {
            // Switch to search phase
            setPhase("search");
            setCurrentQueryIndex(0);
            return 0;
          }
          return next;
        });
      } else {
        setCurrentQueryIndex((prev) => {
          const next = prev + 1;
          if (next >= SEARCH_QUERIES.length) {
            // Loop back to analysis phase
            setPhase("analysis");
            setCurrentStepIndex(0);
            return 0;
          }
          return next;
        });
      }
    };

    // Cycle every 1.5 seconds
    intervalRef.current = setInterval(cycleProgress, 1500);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [phase]);

  const currentStep = ANALYSIS_STEPS[currentStepIndex];
  const currentQuery = SEARCH_QUERIES[currentQueryIndex];

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 10 }}
      className="bg-white dark:bg-navy-800 rounded-xl border border-navy-200 dark:border-navy-700 overflow-hidden shadow-md"
    >
      <div className="px-4 py-3">
        <div className="flex items-center gap-3">
          {/* Icon */}
          <motion.div
            animate={{ scale: [1, 1.1, 1] }}
            transition={{ duration: 1.5, repeat: Infinity }}
            className={`p-2 rounded-lg ${
              phase === "analysis"
                ? "bg-gradient-to-br from-amber-400 to-amber-500"
                : "bg-gradient-to-br from-blue-400 to-blue-500"
            }`}
          >
            {phase === "analysis" ? (
              <Camera className="w-4 h-4 text-white" />
            ) : (
              <Search className="w-4 h-4 text-white" />
            )}
          </motion.div>

          {/* Text */}
          <div className="flex-1 min-w-0">
            <AnimatePresence mode="wait">
              <motion.div
                key={phase === "analysis" ? `step-${currentStepIndex}` : `query-${currentQueryIndex}`}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.2 }}
                className="flex items-center gap-2"
              >
                <span className="text-sm font-medium text-navy-800 dark:text-navy-100 truncate">
                  {phase === "analysis" ? currentStep.label : currentQuery}
                </span>

                {/* Bouncing dots */}
                <div className="flex gap-0.5">
                  {[0, 1, 2].map((i) => (
                    <motion.span
                      key={i}
                      className={`w-1 h-1 rounded-full ${
                        phase === "analysis" ? "bg-amber-500" : "bg-blue-500"
                      }`}
                      animate={{ y: [0, -3, 0] }}
                      transition={{
                        duration: 0.5,
                        repeat: Infinity,
                        delay: i * 0.1,
                      }}
                    />
                  ))}
                </div>
              </motion.div>
            </AnimatePresence>
          </div>

          {/* Spinner */}
          <Loader2 className={`w-4 h-4 animate-spin flex-shrink-0 ${
            phase === "analysis" ? "text-amber-500" : "text-blue-500"
          }`} />
        </div>

        {/* Progress dots indicator */}
        <div className="flex items-center justify-center gap-1.5 mt-2">
          {[...ANALYSIS_STEPS, ...SEARCH_QUERIES].map((_, idx) => {
            const isAnalysisPhase = phase === "analysis";
            const currentIdx = isAnalysisPhase ? currentStepIndex : ANALYSIS_STEPS.length + currentQueryIndex;
            const isActive = idx === currentIdx;

            return (
              <motion.div
                key={idx}
                className={`h-1 rounded-full transition-all duration-300 ${
                  isActive
                    ? (idx < ANALYSIS_STEPS.length ? "bg-amber-500 w-4" : "bg-blue-500 w-4")
                    : "bg-navy-200 dark:bg-navy-700 w-1"
                }`}
              />
            );
          })}
        </div>
      </div>
    </motion.div>
  );
}

export default memo(ContextProgress);
