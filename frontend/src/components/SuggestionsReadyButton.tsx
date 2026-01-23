import { motion, AnimatePresence } from "framer-motion";
import { Sparkles } from "lucide-react";

interface SuggestionsReadyButtonProps {
  onClick: () => void;
  disabled?: boolean;
  isVisible: boolean;
}

export function SuggestionsReadyButton({
  onClick,
  disabled = false,
  isVisible,
}: SuggestionsReadyButtonProps) {
  return (
    <AnimatePresence>
      {isVisible && (
        <motion.button
          onClick={onClick}
          disabled={disabled}
          initial={{ opacity: 0, scale: 0.8, x: -20 }}
          animate={{ opacity: 1, scale: 1, x: 0 }}
          exit={{ opacity: 0, scale: 0.8, x: -20 }}
          transition={{ type: "spring", stiffness: 300, damping: 25 }}
          whileHover={{ scale: disabled ? 1 : 1.05 }}
          whileTap={{ scale: disabled ? 1 : 0.95 }}
          className="relative flex items-center gap-1.5 px-4 py-2 rounded-full text-sm font-semibold
                     bg-gradient-to-r from-amber-500 to-amber-400
                     text-white shadow-lg shadow-amber-500/25
                     hover:shadow-xl hover:shadow-amber-500/30
                     disabled:opacity-50 disabled:cursor-not-allowed
                     transition-shadow flex-shrink-0"
        >
          {/* Pulse ring animation */}
          <motion.span
            className="absolute inset-0 rounded-full bg-amber-400"
            initial={{ opacity: 0.5, scale: 1 }}
            animate={{
              opacity: [0.5, 0, 0.5],
              scale: [1, 1.15, 1],
            }}
            transition={{
              duration: 2,
              repeat: Infinity,
              ease: "easeInOut",
            }}
          />

          {/* Button content */}
          <span className="relative flex items-center gap-1.5">
            <Sparkles className="w-4 h-4" />
            <span className="hidden sm:inline">Ideas Ready</span>
            <span className="sm:hidden">Ideas</span>
          </span>
        </motion.button>
      )}
    </AnimatePresence>
  );
}

export default SuggestionsReadyButton;
