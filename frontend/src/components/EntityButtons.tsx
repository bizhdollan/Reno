import { motion } from "framer-motion";
import { Loader2 } from "lucide-react";

interface Entity {
  type: string;
  label: string;
  confidence: number;
}

interface EntityButtonsProps {
  entities: Entity[];
  isLoading?: boolean;
  onEntityClick: (entity: Entity) => void;
  disabled?: boolean;
}

export function EntityButtons({
  entities,
  isLoading = false,
  onEntityClick,
  disabled = false,
}: EntityButtonsProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center gap-2 py-2">
        <Loader2 className="w-4 h-4 animate-spin text-navy-400" />
        <span className="text-sm text-navy-500 dark:text-navy-400">
          Detecting room elements...
        </span>
      </div>
    );
  }

  if (entities.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-wrap gap-2 justify-center">
      {entities.map((entity, index) => (
        <motion.button
          key={entity.type}
          onClick={() => onEntityClick(entity)}
          disabled={disabled}
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.2, delay: index * 0.05 }}
          whileHover={{ scale: disabled ? 1 : 1.05 }}
          whileTap={{ scale: disabled ? 1 : 0.95 }}
          className={`
            px-4 py-2
            bg-white/90 dark:bg-navy-800/90
            backdrop-blur-sm
            text-navy-700 dark:text-white
            text-sm font-medium
            rounded-full
            shadow-lg
            hover:bg-white dark:hover:bg-navy-700
            transition-colors
            border border-navy-200 dark:border-navy-600
            disabled:opacity-50 disabled:cursor-not-allowed
          `}
          title={`Change ${entity.label}`}
        >
          Change {entity.label}
        </motion.button>
      ))}
    </div>
  );
}

export default EntityButtons;
