import { motion } from "framer-motion";

interface Step {
  key: string;
  label: string;
}

interface StepIndicatorProps {
  steps: Step[];
  currentStep: string;
  compact?: boolean;
}

export function StepIndicator({ steps, currentStep, compact = false }: StepIndicatorProps) {
  const currentIndex = steps.findIndex((s) => s.key === currentStep);
  const currentStepData = steps[currentIndex];

  if (compact) {
    // Just show dots
    return (
      <div className="flex items-center gap-1.5">
        {steps.map((step, index) => {
          const isCompleted = index < currentIndex;
          const isCurrent = index === currentIndex;

          return (
            <motion.div
              key={step.key}
              initial={false}
              animate={{
                scale: isCurrent ? 1.3 : 1,
                backgroundColor: isCompleted
                  ? "rgb(16, 185, 129)" // emerald-500
                  : isCurrent
                  ? "rgb(245, 158, 11)" // amber-500
                  : "rgb(203, 213, 225)", // slate-300
              }}
              className="w-2 h-2 rounded-full"
              title={step.label}
            />
          );
        })}
      </div>
    );
  }

  // Show dots with current step label
  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-1.5">
        {steps.map((step, index) => {
          const isCompleted = index < currentIndex;
          const isCurrent = index === currentIndex;

          return (
            <motion.div
              key={step.key}
              initial={false}
              animate={{
                scale: isCurrent ? 1.3 : 1,
                backgroundColor: isCompleted
                  ? "rgb(16, 185, 129)" // emerald-500
                  : isCurrent
                  ? "rgb(245, 158, 11)" // amber-500
                  : "rgb(203, 213, 225)", // slate-300
              }}
              className="w-2 h-2 rounded-full"
              title={step.label}
            />
          );
        })}
      </div>
      {currentStepData && (
        <span className="text-xs font-medium text-navy-600 dark:text-navy-300">
          {currentStepData.label}
        </span>
      )}
    </div>
  );
}

export default StepIndicator;
