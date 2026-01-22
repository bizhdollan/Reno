import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Settings2,
  Plus,
  X,
  ChevronDown,
  ChevronUp,
  Palette,
  Hammer,
  Ban,
  Heart,
  Tag,
  Sparkles,
} from "lucide-react";

// Preference categories
const CATEGORIES = [
  { value: "style", label: "Style", icon: Palette, color: "bg-purple-500" },
  { value: "material", label: "Material", icon: Hammer, color: "bg-blue-500" },
  { value: "color", label: "Color", icon: Sparkles, color: "bg-pink-500" },
  { value: "budget", label: "Budget", icon: Tag, color: "bg-orange-500" },
  { value: "avoid", label: "Avoid", icon: Ban, color: "bg-red-500" },
  { value: "must_have", label: "Must Have", icon: Heart, color: "bg-green-500" },
] as const;

type CategoryValue = (typeof CATEGORIES)[number]["value"];

interface PreferenceItem {
  id: string;
  category: CategoryValue;
  content: string;
  created_at?: string;
}

interface MyPreferencesPanelProps {
  preferences: PreferenceItem[];
  onAddPreference: (category: string, content: string) => void;
  onRemovePreference: (preferenceId: string) => void;
  isLoading?: boolean;
}

export function MyPreferencesPanel({
  preferences,
  onAddPreference,
  onRemovePreference,
  isLoading = false,
}: MyPreferencesPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isAdding, setIsAdding] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<CategoryValue>("style");
  const [content, setContent] = useState("");

  const getCategoryConfig = useCallback((category: string) => {
    return CATEGORIES.find((c) => c.value === category) || CATEGORIES[0];
  }, []);

  const handleAdd = useCallback(() => {
    if (!content.trim()) return;
    onAddPreference(selectedCategory, content.trim());
    setContent("");
    setIsAdding(false);
  }, [selectedCategory, content, onAddPreference]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleAdd();
      } else if (e.key === "Escape") {
        setIsAdding(false);
        setContent("");
      }
    },
    [handleAdd]
  );

  return (
    <div className="relative">
      {/* Toggle Button */}
      <motion.button
        onClick={() => setIsExpanded(!isExpanded)}
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-colors ${
          isExpanded
            ? "bg-amber-500 text-navy-900"
            : "bg-navy-100 dark:bg-navy-700 text-navy-600 dark:text-navy-300 hover:bg-navy-200 dark:hover:bg-navy-600"
        }`}
        title="My Preferences"
      >
        <Settings2 size={18} />
        {preferences.length > 0 && (
          <span className="text-sm font-medium">{preferences.length}</span>
        )}
        {isExpanded ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
      </motion.button>

      {/* Expanded Panel */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.95 }}
            transition={{ duration: 0.2 }}
            className="absolute bottom-full mb-2 right-0 w-80 bg-white dark:bg-navy-800 rounded-xl shadow-xl border border-navy-100 dark:border-navy-700 overflow-hidden"
          >
            {/* Header */}
            <div className="px-4 py-3 border-b border-navy-100 dark:border-navy-700 flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-navy-900 dark:text-white text-sm">
                  My Preferences
                </h3>
                <p className="text-xs text-navy-500 dark:text-navy-400">
                  Personalize your renovation experience
                </p>
              </div>
              <button
                onClick={() => setIsExpanded(false)}
                className="p-1 rounded-md hover:bg-navy-100 dark:hover:bg-navy-700 transition-colors"
              >
                <X size={16} className="text-navy-400" />
              </button>
            </div>

            {/* Preferences List */}
            <div className="max-h-64 overflow-y-auto">
              {preferences.length === 0 ? (
                <div className="p-4 text-center text-navy-400 dark:text-navy-500 text-sm">
                  No preferences added yet.
                  <br />
                  Tell us what you like!
                </div>
              ) : (
                <div className="p-2 space-y-2">
                  {preferences.map((pref) => {
                    const config = getCategoryConfig(pref.category);
                    const Icon = config.icon;
                    return (
                      <motion.div
                        key={pref.id}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: 10 }}
                        className="flex items-start gap-2 p-2 bg-navy-50 dark:bg-navy-900 rounded-lg group"
                      >
                        <div
                          className={`p-1 rounded ${config.color} text-white flex-shrink-0`}
                        >
                          <Icon size={12} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <span className="text-xs font-medium text-navy-500 dark:text-navy-400 uppercase">
                            {config.label}
                          </span>
                          <p className="text-sm text-navy-800 dark:text-navy-200 break-words">
                            {pref.content}
                          </p>
                        </div>
                        <button
                          onClick={() => onRemovePreference(pref.id)}
                          disabled={isLoading}
                          className="p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-navy-200 dark:hover:bg-navy-700 transition-all disabled:opacity-50"
                        >
                          <X size={14} className="text-navy-400" />
                        </button>
                      </motion.div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Add Preference Section */}
            <div className="border-t border-navy-100 dark:border-navy-700 p-3">
              <AnimatePresence mode="wait">
                {isAdding ? (
                  <motion.div
                    key="add-form"
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="space-y-3"
                  >
                    {/* Category Selection */}
                    <div className="flex flex-wrap gap-1.5">
                      {CATEGORIES.map((cat) => {
                        const Icon = cat.icon;
                        return (
                          <button
                            key={cat.value}
                            onClick={() => setSelectedCategory(cat.value)}
                            className={`flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium transition-colors ${
                              selectedCategory === cat.value
                                ? `${cat.color} text-white`
                                : "bg-navy-100 dark:bg-navy-700 text-navy-600 dark:text-navy-300 hover:bg-navy-200 dark:hover:bg-navy-600"
                            }`}
                          >
                            <Icon size={12} />
                            {cat.label}
                          </button>
                        );
                      })}
                    </div>

                    {/* Input */}
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={content}
                        onChange={(e) => setContent(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder={`What ${getCategoryConfig(selectedCategory).label.toLowerCase()} do you prefer?`}
                        autoFocus
                        disabled={isLoading}
                        className="flex-1 px-3 py-2 bg-navy-50 dark:bg-navy-900 border border-navy-200 dark:border-navy-700 rounded-lg text-sm text-navy-900 dark:text-white placeholder-navy-400 focus:outline-none focus:ring-2 focus:ring-amber-500 disabled:opacity-50"
                      />
                      <button
                        onClick={handleAdd}
                        disabled={!content.trim() || isLoading}
                        className="px-3 py-2 bg-amber-500 text-navy-900 rounded-lg text-sm font-medium hover:bg-amber-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        Add
                      </button>
                    </div>

                    {/* Cancel */}
                    <button
                      onClick={() => {
                        setIsAdding(false);
                        setContent("");
                      }}
                      className="w-full text-center text-xs text-navy-400 hover:text-navy-600 dark:hover:text-navy-300"
                    >
                      Cancel
                    </button>
                  </motion.div>
                ) : (
                  <motion.button
                    key="add-button"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    onClick={() => setIsAdding(true)}
                    disabled={isLoading}
                    className="w-full flex items-center justify-center gap-2 py-2 text-sm text-amber-600 dark:text-amber-400 hover:text-amber-700 dark:hover:text-amber-300 font-medium transition-colors disabled:opacity-50"
                  >
                    <Plus size={16} />
                    Add Preference
                  </motion.button>
                )}
              </AnimatePresence>
            </div>

            {/* Examples */}
            <div className="px-4 py-2 bg-navy-50 dark:bg-navy-900 border-t border-navy-100 dark:border-navy-700">
              <p className="text-xs text-navy-400 dark:text-navy-500">
                Examples: "modern style", "white cabinets", "no carpet", "under $50k"
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default MyPreferencesPanel;
