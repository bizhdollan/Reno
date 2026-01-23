import { motion } from "framer-motion";

export interface DetectedEntity {
  type: string;
  label: string;
  confidence: number;
}

interface QuickActionButtonsProps {
  onAction: (message: string, actionId: string) => void;
  disabled?: boolean;
  entities?: DetectedEntity[];
}

export function QuickActionButtons({
  onAction,
  disabled = false,
  entities = [],
}: QuickActionButtonsProps) {
  // Build action buttons dynamically (always reusable)
  const actions: { id: string; label: string; message: string }[] = [];

  // Add entity-based buttons (NO hiding after click)
  entities.slice(0, 5).forEach((entity) => {
    const actionId = `entity-${entity.type}`;
    const message = `Change the ${entity.label.toLowerCase()} material, color and style`;

    actions.push({
      id: actionId,
      label: `Change ${entity.label}`,
      message,
    });
  });

  // Don't render if no actions available
  if (actions.length === 0) {
    return null;
  }

  const getButtonClasses = () => {
    return "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-colors whitespace-nowrap bg-teal-100 dark:bg-teal-500/20 text-teal-700 dark:text-teal-400 hover:bg-teal-200 dark:hover:bg-teal-500/30";
  };

  return (
    <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-hide">
      {actions.map((action, index) => (
        <motion.button
          key={action.id}
          onClick={() => onAction(action.message, action.id)}
          disabled={disabled}
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.2, delay: index * 0.05 }}
          whileHover={{ scale: disabled ? 1 : 1.02 }}
          whileTap={{ scale: disabled ? 1 : 0.98 }}
          className={`${getButtonClasses()} disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0`}
        >
          <span>{action.label}</span>
        </motion.button>
      ))}
    </div>
  );
}

export default QuickActionButtons;
