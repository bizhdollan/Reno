import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Image as ImageIcon, X, ZoomIn, Sparkles, ChevronLeft, ChevronDown, FileText } from "lucide-react";
import { CanvasImage } from "./Canvas";

interface MobileCanvasExpanderProps {
  images: CanvasImage[];
  selectedImageId?: string;
  onSelectImage: (id: string) => void;
  onImageClick?: (url: string) => void;
  isGenerating?: boolean;
  isAnalyzing?: boolean;
  showContinueButton?: boolean;
  onContinue?: () => void;
}

export function MobileCanvasExpander({
  images,
  selectedImageId,
  onSelectImage,
  onImageClick,
  isGenerating = false,
  isAnalyzing = false,
  showContinueButton = false,
  onContinue,
}: MobileCanvasExpanderProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isChangesExpanded, setIsChangesExpanded] = useState(true);

  const selectedImage = images.find((img) => img.id === selectedImageId) || images[0];
  const hasChanges = selectedImage?.type === "generated" && selectedImage?.changes && selectedImage.changes.length > 0;

  const toggleExpanded = useCallback(() => {
    setIsExpanded((prev) => !prev);
  }, []);

  // Don't show if no images
  if (images.length === 0) {
    return null;
  }

  return (
    <>
      {/* Floating Button - Fixed on left side */}
      <motion.button
        onClick={toggleExpanded}
        className="lg:hidden fixed left-0 top-1/2 -translate-y-1/2 z-40 flex items-center gap-1 pl-2 pr-3 py-3 bg-amber-500 text-white rounded-r-xl shadow-lg"
        whileHover={{ x: 4 }}
        whileTap={{ scale: 0.95 }}
        initial={{ x: -10, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        transition={{ delay: 0.5 }}
      >
        <ChevronLeft className={`w-4 h-4 transition-transform ${isExpanded ? "rotate-180" : ""}`} />
        <div className="relative">
          <ImageIcon className="w-5 h-5" />
          {/* Badge showing image count */}
          <span className="absolute -top-1.5 -right-1.5 w-4 h-4 bg-white text-amber-600 text-[10px] font-bold rounded-full flex items-center justify-center">
            {images.length}
          </span>
        </div>
      </motion.button>

      {/* Expanded Canvas Panel */}
      <AnimatePresence>
        {isExpanded && (
          <>
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="lg:hidden fixed inset-0 bg-black/50 z-40"
              onClick={toggleExpanded}
            />

            {/* Canvas Panel - Slides from left */}
            <motion.div
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "spring", damping: 30, stiffness: 300 }}
              className="lg:hidden fixed inset-y-0 left-0 w-[85%] max-w-md z-50 bg-white dark:bg-navy-900 shadow-2xl flex flex-col"
            >
              {/* Header */}
              <div className="flex-shrink-0 flex items-center justify-between p-4 border-b border-navy-200 dark:border-navy-700">
                <h2 className="text-lg font-bold text-navy-900 dark:text-white">Canvas</h2>
                <button
                  onClick={toggleExpanded}
                  className="p-2 text-navy-500 hover:text-navy-700 dark:text-navy-400 dark:hover:text-navy-200 hover:bg-navy-100 dark:hover:bg-navy-700 rounded-full transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Main Image */}
              <div className="flex-1 relative flex items-center justify-center p-4 overflow-hidden bg-navy-50 dark:bg-navy-800/50">
                <AnimatePresence mode="wait">
                  {selectedImage && (
                    <motion.div
                      key={selectedImage.id}
                      initial={{ opacity: 0, scale: 0.95 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.95 }}
                      transition={{ duration: 0.2 }}
                      className="relative max-w-full max-h-full"
                    >
                      <img
                        src={selectedImage.url}
                        alt={selectedImage.label || "Preview"}
                        className="max-w-full max-h-[50vh] object-contain rounded-xl shadow-lg"
                        onClick={() => onImageClick?.(selectedImage.url)}
                      />

                      {/* Badge for generated images */}
                      {selectedImage.type === "generated" && (
                        <div className="absolute top-2 left-2 flex items-center gap-1 px-2 py-0.5 bg-gradient-to-r from-purple-500 to-purple-600 text-white text-xs font-medium rounded-full shadow">
                          <Sparkles className="w-3 h-3" />
                          Generated
                        </div>
                      )}

                      {/* Zoom indicator */}
                      <button
                        onClick={() => onImageClick?.(selectedImage.url)}
                        className="absolute bottom-2 right-2 p-2 bg-white/90 dark:bg-navy-800/90 rounded-full shadow-lg"
                      >
                        <ZoomIn className="w-4 h-4 text-navy-700 dark:text-white" />
                      </button>
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Loading overlay - analyzing or generating */}
                {(isAnalyzing || isGenerating) && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="absolute inset-0 flex items-center justify-center bg-white/80 dark:bg-navy-900/80 backdrop-blur-sm"
                  >
                    <div className="flex flex-col items-center gap-2">
                      <motion.div
                        animate={{ rotate: 360 }}
                        transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                      >
                        <Sparkles className="w-8 h-8 text-amber-500" />
                      </motion.div>
                      <p className="text-sm font-medium text-navy-600 dark:text-navy-300">
                        {isAnalyzing ? "Analyzing..." : "Generating..."}
                      </p>
                    </div>
                  </motion.div>
                )}
              </div>

              {/* Changes Panel - Collapsible section showing what changed */}
              {hasChanges && (
                <div className="flex-shrink-0 border-t border-navy-200 dark:border-navy-700 bg-white dark:bg-navy-800">
                  <button
                    onClick={() => setIsChangesExpanded(!isChangesExpanded)}
                    className="w-full px-4 py-2 flex items-center justify-between text-left"
                  >
                    <div className="flex items-center gap-2">
                      <FileText className="w-4 h-4 text-purple-500" />
                      <span className="text-sm font-medium text-navy-700 dark:text-navy-200">
                        Changes
                      </span>
                      <span className="text-xs text-navy-400">
                        ({selectedImage.changes?.length})
                      </span>
                    </div>
                    <motion.div
                      animate={{ rotate: isChangesExpanded ? 180 : 0 }}
                      transition={{ duration: 0.2 }}
                    >
                      <ChevronDown className="w-4 h-4 text-navy-400" />
                    </motion.div>
                  </button>

                  <AnimatePresence>
                    {isChangesExpanded && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="overflow-hidden"
                      >
                        <ul className="px-4 pb-3 space-y-1">
                          {selectedImage.changes?.map((change, idx) => (
                            <li key={idx} className="flex items-start gap-2 text-xs text-navy-600 dark:text-navy-300">
                              <span className="text-purple-500 mt-0.5">•</span>
                              <span>{change}</span>
                            </li>
                          ))}
                        </ul>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              )}

              {/* Thumbnail Gallery */}
              <div className="flex-shrink-0 border-t border-navy-200 dark:border-navy-700 bg-white dark:bg-navy-800 p-3">
                <div className="flex gap-2 overflow-x-auto pb-1">
                  {images.map((img) => (
                    <button
                      key={img.id}
                      onClick={() => onSelectImage(img.id)}
                      className={`relative flex-shrink-0 w-14 h-14 rounded-lg overflow-hidden border-2 transition-all ${
                        selectedImage?.id === img.id
                          ? "border-amber-500 ring-2 ring-amber-200 dark:ring-amber-500/30"
                          : "border-transparent hover:border-navy-300 dark:hover:border-navy-500"
                      }`}
                    >
                      <img
                        src={img.url}
                        alt={img.label || "Thumbnail"}
                        className="w-full h-full object-cover"
                      />
                      {img.type === "generated" && (
                        <div className="absolute top-0.5 right-0.5 w-3 h-3 bg-purple-500 rounded-full flex items-center justify-center">
                          <Sparkles className="w-2 h-2 text-white" />
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              </div>

              {/* Continue Button */}
              {showContinueButton && onContinue && (
                <div className="flex-shrink-0 p-4 border-t border-navy-200 dark:border-navy-700 bg-white dark:bg-navy-800">
                  <motion.button
                    onClick={() => {
                      onContinue();
                      setIsExpanded(false);
                    }}
                    whileTap={{ scale: 0.98 }}
                    className="w-full py-3 px-6 bg-gradient-to-r from-amber-500 to-amber-400 text-navy-900 font-semibold rounded-xl shadow-lg shadow-amber-500/25"
                  >
                    Continue to Estimate
                  </motion.button>
                </div>
              )}
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}

export default MobileCanvasExpander;
