/**
 * ContextProgress Component
 *
 * Claude Code-style streaming progress indicator for context gathering.
 * Shows real-time analysis and search progress during image upload.
 */

import { memo, useEffect, useState, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Camera,
  Search,
  CheckCircle2,
  Loader2,
  ExternalLink,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { ContextStream, ContextEvent } from "../lib/api";

// ==================== TYPES ====================

interface AnalysisStep {
  id: string;
  label: string;
  status: "pending" | "active" | "completed";
  details?: string;
}

interface SearchSource {
  title: string;
  url: string;
  snippet?: string;
}

interface ContextProgressProps {
  projectId: string;
  onContextReady: () => void;
  onError?: (error: string) => void;
}

// ==================== STEP INDICATOR ====================

const StepIndicator = memo(function StepIndicator({
  step,
}: {
  step: AnalysisStep;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      className="flex items-center gap-2 py-1"
    >
      {step.status === "completed" ? (
        <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0" />
      ) : step.status === "active" ? (
        <Loader2 className="w-4 h-4 text-amber-500 animate-spin flex-shrink-0" />
      ) : (
        <div className="w-4 h-4 rounded-full border border-navy-300 dark:border-navy-600 flex-shrink-0" />
      )}
      <span
        className={`text-sm ${
          step.status === "completed"
            ? "text-navy-600 dark:text-navy-400"
            : step.status === "active"
            ? "text-navy-800 dark:text-navy-200 font-medium"
            : "text-navy-400 dark:text-navy-500"
        }`}
      >
        {step.label}
      </span>
      {step.details && step.status === "active" && (
        <span className="text-xs text-navy-400 dark:text-navy-500 ml-1">
          ({step.details})
        </span>
      )}
    </motion.div>
  );
});

// ==================== SOURCE ITEM ====================

const SourceItem = memo(function SourceItem({
  source,
  index,
}: {
  source: SearchSource;
  index: number;
}) {
  return (
    <motion.a
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      className="flex items-start gap-2 py-1.5 px-2 rounded-lg hover:bg-navy-50 dark:hover:bg-navy-800/50 transition-colors group"
    >
      <ExternalLink className="w-3 h-3 text-navy-400 mt-0.5 flex-shrink-0 group-hover:text-amber-500" />
      <div className="flex-1 min-w-0">
        <span className="text-xs text-navy-600 dark:text-navy-300 line-clamp-1 group-hover:text-amber-600 dark:group-hover:text-amber-400">
          {source.title}
        </span>
        {source.snippet && (
          <span className="text-xs text-navy-400 dark:text-navy-500 line-clamp-1 mt-0.5">
            {source.snippet}
          </span>
        )}
      </div>
    </motion.a>
  );
});

// ==================== MAIN COMPONENT ====================

export function ContextProgress({
  projectId,
  onContextReady,
  onError,
}: ContextProgressProps) {
  const [phase, setPhase] = useState<"analysis" | "search" | "ready">("analysis");
  const [analysisSteps, setAnalysisSteps] = useState<AnalysisStep[]>([
    { id: "load", label: "Loading images", status: "pending" },
    { id: "extract", label: "Extracting room details", status: "pending" },
    { id: "context", label: "Building search context", status: "pending" },
  ]);
  // Note: searchQueries captures all planned queries from search_start event
  // Currently we just show currentQuery, but this could be used for a progress indicator
  const [, setSearchQueries] = useState<string[]>([]);
  const [currentQuery, setCurrentQuery] = useState<string | null>(null);
  const [sources, setSources] = useState<SearchSource[]>([]);
  const [showSources, setShowSources] = useState(false);
  const [stats, setStats] = useState({ styles: 0, materials: 0 });

  const streamRef = useRef<ContextStream | null>(null);

  const handleEvent = useCallback((event: ContextEvent) => {
    console.log("[ContextProgress] Event:", event.type, event.data);

    switch (event.type) {
      case "analysis_progress":
        const step = event.data.step;
        if (step === "loading_image") {
          setAnalysisSteps((prev) =>
            prev.map((s) =>
              s.id === "load" ? { ...s, status: "active" } : s
            )
          );
        } else if (step === "extracting_data") {
          setAnalysisSteps((prev) =>
            prev.map((s) =>
              s.id === "load"
                ? { ...s, status: "completed" }
                : s.id === "extract"
                ? { ...s, status: "active" }
                : s
            )
          );
        } else if (step === "completed") {
          setAnalysisSteps((prev) =>
            prev.map((s) =>
              s.id === "extract"
                ? { ...s, status: "completed" }
                : s.id === "context"
                ? { ...s, status: "active" }
                : s
            )
          );
        }
        break;

      case "analysis_complete":
        setAnalysisSteps((prev) =>
          prev.map((s) => ({ ...s, status: "completed" }))
        );
        setPhase("search");
        break;

      case "search_start":
        // Transition to search phase (handles case where analysis events were missed)
        setAnalysisSteps((prev) =>
          prev.map((s) => ({ ...s, status: "completed" }))
        );
        setPhase("search");
        setSearchQueries(event.data.queries || []);
        break;

      case "search_query":
        // Ensure we're in search phase
        setPhase((currentPhase) => currentPhase === "analysis" ? "search" : currentPhase);
        setCurrentQuery(event.data.query || null);
        break;

      case "search_result":
        if (event.data.title && event.data.url) {
          setSources((prev) => [
            ...prev,
            {
              title: event.data.title!,
              url: event.data.url!,
              snippet: event.data.snippet,
            },
          ]);
        }
        break;

      case "search_complete":
        setStats({
          styles: event.data.styles_found || 0,
          materials: event.data.materials_found || 0,
        });
        break;

      case "context_ready":
        setPhase("ready");
        setCurrentQuery(null);
        setTimeout(() => {
          onContextReady();
        }, 500);
        break;

      case "error":
        onError?.(event.data.message || "An error occurred");
        break;

      default:
        break;
    }
  }, [onContextReady, onError]);

  useEffect(() => {
    // Connect to SSE stream
    streamRef.current = new ContextStream();
    streamRef.current.connect(projectId, handleEvent);

    return () => {
      streamRef.current?.disconnect();
    };
  }, [projectId, handleEvent]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white dark:bg-navy-800 rounded-xl border border-navy-200 dark:border-navy-700 overflow-hidden shadow-sm"
    >
      {/* Header */}
      <div className="px-4 py-3 border-b border-navy-100 dark:border-navy-700 bg-navy-50/50 dark:bg-navy-900/50">
        <div className="flex items-center gap-2">
          <div className="relative">
            {phase === "analysis" && (
              <Camera className="w-4 h-4 text-amber-500" />
            )}
            {phase === "search" && (
              <Search className="w-4 h-4 text-blue-500" />
            )}
            {phase === "ready" && (
              <CheckCircle2 className="w-4 h-4 text-emerald-500" />
            )}
            {phase !== "ready" && (
              <span className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-amber-500 rounded-full animate-pulse" />
            )}
          </div>
          <span className="text-sm font-medium text-navy-700 dark:text-navy-200">
            {phase === "analysis" && "Analyzing your space..."}
            {phase === "search" && "Finding local inspiration..."}
            {phase === "ready" && "Context ready!"}
          </span>
        </div>
      </div>

      {/* Content */}
      <div className="px-4 py-3">
        {/* Analysis Steps */}
        <AnimatePresence mode="wait">
          {phase === "analysis" && (
            <motion.div
              key="analysis"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="space-y-1"
            >
              {analysisSteps.map((step) => (
                <StepIndicator key={step.id} step={step} />
              ))}
            </motion.div>
          )}

          {phase === "search" && (
            <motion.div
              key="search"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="space-y-3"
            >
              {/* Current Query */}
              {currentQuery && (
                <div className="flex items-center gap-2 text-sm">
                  <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />
                  <span className="text-navy-600 dark:text-navy-300 truncate">
                    Searching: {currentQuery.slice(0, 50)}...
                  </span>
                </div>
              )}

              {/* Sources Found */}
              {sources.length > 0 && (
                <div>
                  <button
                    onClick={() => setShowSources(!showSources)}
                    className="flex items-center gap-2 text-sm text-navy-500 dark:text-navy-400 hover:text-navy-700 dark:hover:text-navy-300"
                  >
                    {showSources ? (
                      <ChevronUp className="w-4 h-4" />
                    ) : (
                      <ChevronDown className="w-4 h-4" />
                    )}
                    <span>{sources.length} sources found</span>
                  </button>

                  <AnimatePresence>
                    {showSources && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="overflow-hidden mt-2 max-h-32 overflow-y-auto"
                      >
                        {sources.slice(0, 6).map((source, idx) => (
                          <SourceItem key={idx} source={source} index={idx} />
                        ))}
                        {sources.length > 6 && (
                          <span className="text-xs text-navy-400 dark:text-navy-500 px-2">
                            +{sources.length - 6} more
                          </span>
                        )}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              )}
            </motion.div>
          )}

          {phase === "ready" && (
            <motion.div
              key="ready"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex items-center gap-3"
            >
              <CheckCircle2 className="w-5 h-5 text-emerald-500" />
              <div className="text-sm">
                <span className="text-navy-700 dark:text-navy-200 font-medium">
                  Ready to suggest designs
                </span>
                {(stats.styles > 0 || stats.materials > 0) && (
                  <span className="text-navy-400 dark:text-navy-500 ml-2">
                    ({stats.styles} styles, {stats.materials} materials found)
                  </span>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

export default memo(ContextProgress);
