import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ZoomIn, ChevronRight, Image as ImageIcon, Sparkles, ChevronDown, FileText } from "lucide-react";

export interface CanvasImage {
  id: string;
  url: string;
  type: "uploaded" | "generated";
  label?: string;
  timestamp?: string;
  changes?: string[]; // List of changes made in this generated image
}

interface CanvasProps {
  images: CanvasImage[];
  selectedImageId?: string;
  onSelectImage: (id: string) => void;
  onImageClick?: (url: string) => void;
  onContinue?: () => void;
  showContinueButton?: boolean;
  isGenerating?: boolean;
  isAnalyzing?: boolean; // True when analyzing uploaded images (before any generation)
}

export function Canvas({
  images,
  selectedImageId,
  onSelectImage,
  onImageClick,
  onContinue,
  showContinueButton = false,
  isGenerating = false,
  isAnalyzing = false,
}: CanvasProps) {
  const [hoveredThumbnail, setHoveredThumbnail] = useState<string | null>(null);
  const [isChangesExpanded, setIsChangesExpanded] = useState(true);

  const selectedImage = images.find((img) => img.id === selectedImageId) || images[0];
  const hasChanges = selectedImage?.type === "generated" && selectedImage?.changes && selectedImage.changes.length > 0;

  const handleThumbnailClick = useCallback(
    (id: string) => {
      onSelectImage(id);
    },
    [onSelectImage]
  );

  if (images.length === 0) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-navy-400 dark:text-navy-500 p-8">
        <motion.div
          animate={{ scale: [1, 1.05, 1], opacity: [0.5, 0.7, 0.5] }}
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
        >
          <ImageIcon className="w-16 h-16 mb-4" />
        </motion.div>
        <p className="text-lg font-medium">Canvas</p>
        <p className="text-sm mt-1 text-center">Your images and generated designs<br />will appear here</p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-navy-50 dark:bg-navy-900/50">
      {/* Main Image Preview */}
      <div className="flex-1 relative flex items-center justify-center p-4 overflow-hidden">
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
                className="max-w-full max-h-[60vh] object-contain rounded-xl shadow-lg cursor-pointer hover:shadow-xl transition-shadow"
                onClick={() => onImageClick?.(selectedImage.url)}
              />

              {/* Badge for generated images */}
              {selectedImage.type === "generated" && (
                <div className="absolute top-3 left-3 flex items-center gap-1.5 px-2.5 py-1 bg-gradient-to-r from-purple-500 to-purple-600 text-white text-xs font-medium rounded-full shadow-md">
                  <Sparkles className="w-3 h-3" />
                  Generated
                </div>
              )}

              {/* Zoom indicator on hover */}
              <motion.div
                initial={{ opacity: 0 }}
                whileHover={{ opacity: 1 }}
                className="absolute inset-0 flex items-center justify-center bg-black/20 rounded-xl opacity-0 hover:opacity-100 transition-opacity cursor-pointer"
                onClick={() => onImageClick?.(selectedImage.url)}
              >
                <div className="bg-white/90 dark:bg-navy-800/90 p-3 rounded-full shadow-lg">
                  <ZoomIn className="w-6 h-6 text-navy-700 dark:text-white" />
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Loading overlay - shows during analyzing or generating */}
        {(isAnalyzing || isGenerating) && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="absolute inset-0 flex items-center justify-center bg-white/80 dark:bg-navy-900/80 backdrop-blur-sm"
          >
            <div className="flex flex-col items-center gap-3">
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
              >
                <Sparkles className="w-10 h-10 text-amber-500" />
              </motion.div>
              <p className="text-sm font-medium text-navy-600 dark:text-navy-300">
                {isAnalyzing ? "Analyzing your room..." : "Generating your design..."}
              </p>
            </div>
          </motion.div>
        )}
      </div>

      {/* Changes Panel - Collapsible section showing what changed in this design */}
      {hasChanges && (
        <div className="flex-shrink-0 border-t border-navy-200 dark:border-navy-700 bg-white dark:bg-navy-800">
          <button
            onClick={() => setIsChangesExpanded(!isChangesExpanded)}
            className="w-full px-4 py-2.5 flex items-center justify-between text-left hover:bg-navy-50 dark:hover:bg-navy-700/50 transition-colors"
          >
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-purple-500" />
              <span className="text-sm font-medium text-navy-700 dark:text-navy-200">
                Changes in this design
              </span>
              <span className="text-xs text-navy-400 dark:text-navy-500">
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
                <ul className="px-4 pb-3 space-y-1.5">
                  {selectedImage.changes?.map((change, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-sm text-navy-600 dark:text-navy-300">
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
            <motion.button
              key={img.id}
              onClick={() => handleThumbnailClick(img.id)}
              onMouseEnter={() => setHoveredThumbnail(img.id)}
              onMouseLeave={() => setHoveredThumbnail(null)}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className={`relative flex-shrink-0 w-16 h-16 rounded-lg overflow-hidden border-2 transition-all ${
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
              {/* Generated badge on thumbnail */}
              {img.type === "generated" && (
                <div className="absolute top-0.5 right-0.5 w-4 h-4 bg-purple-500 rounded-full flex items-center justify-center">
                  <Sparkles className="w-2.5 h-2.5 text-white" />
                </div>
              )}
              {/* Hover label */}
              <AnimatePresence>
                {hoveredThumbnail === img.id && img.label && (
                  <motion.div
                    initial={{ opacity: 0, y: 5 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 5 }}
                    className="absolute inset-x-0 bottom-0 bg-black/70 text-white text-[10px] text-center py-0.5 truncate"
                  >
                    {img.label}
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.button>
          ))}
        </div>
      </div>

      {/* Continue Button */}
      {showContinueButton && onContinue && (
        <div className="flex-shrink-0 p-4 border-t border-navy-200 dark:border-navy-700 bg-white dark:bg-navy-800">
          <motion.button
            onClick={onContinue}
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.99 }}
            className="w-full py-3 px-6 bg-gradient-to-r from-amber-500 to-amber-400 text-navy-900 font-semibold rounded-xl shadow-lg shadow-amber-500/25 hover:shadow-xl hover:shadow-amber-500/30 transition-all flex items-center justify-center gap-2"
          >
            Continue to Estimate
            <ChevronRight className="w-5 h-5" />
          </motion.button>
        </div>
      )}
    </div>
  );
}

export default Canvas;
