import { useState, useCallback, useRef } from "react";
import { motion, AnimatePresence, PanInfo, useAnimation } from "framer-motion";
import { ChevronUp, ChevronDown, X, ZoomIn, Sparkles, Image as ImageIcon } from "lucide-react";

interface CanvasImage {
  id: string;
  url: string;
  type: "uploaded" | "generated";
  label?: string;
}

interface MobileCanvasSheetProps {
  images: CanvasImage[];
  selectedImageId?: string;
  onSelectImage: (id: string) => void;
  onImageClick?: (url: string) => void;
  isGenerating?: boolean;
}

type SheetState = "collapsed" | "expanded";

export function MobileCanvasSheet({
  images,
  selectedImageId,
  onSelectImage,
  onImageClick,
  isGenerating = false,
}: MobileCanvasSheetProps) {
  const [sheetState, setSheetState] = useState<SheetState>("collapsed");
  const controls = useAnimation();
  const constraintsRef = useRef<HTMLDivElement>(null);

  const selectedImage = images.find((img) => img.id === selectedImageId) || images[0];

  const handleDragEnd = useCallback(
    (_: any, info: PanInfo) => {
      const threshold = 50;
      if (sheetState === "collapsed" && info.offset.y < -threshold) {
        setSheetState("expanded");
      } else if (sheetState === "expanded" && info.offset.y > threshold) {
        setSheetState("collapsed");
      }
    },
    [sheetState]
  );

  const toggleSheet = useCallback(() => {
    setSheetState((prev) => (prev === "collapsed" ? "expanded" : "collapsed"));
  }, []);

  if (images.length === 0) {
    return null; // Don't show bottom sheet if no images
  }

  return (
    <>
      {/* Overlay when expanded */}
      <AnimatePresence>
        {sheetState === "expanded" && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 z-40 lg:hidden"
            onClick={() => setSheetState("collapsed")}
          />
        )}
      </AnimatePresence>

      {/* Bottom Sheet */}
      <motion.div
        ref={constraintsRef}
        className="fixed bottom-0 left-0 right-0 z-50 lg:hidden"
        initial={false}
        animate={{
          height: sheetState === "expanded" ? "85vh" : "auto",
        }}
        transition={{ type: "spring", damping: 30, stiffness: 300 }}
      >
        <motion.div
          className="bg-white dark:bg-navy-800 rounded-t-2xl shadow-2xl border-t border-navy-200 dark:border-navy-700 h-full flex flex-col"
          drag="y"
          dragConstraints={{ top: 0, bottom: 0 }}
          dragElastic={0.2}
          onDragEnd={handleDragEnd}
        >
          {/* Handle Bar */}
          <div
            className="flex-shrink-0 flex flex-col items-center pt-2 pb-1 cursor-grab active:cursor-grabbing"
            onClick={toggleSheet}
          >
            <div className="w-12 h-1.5 bg-navy-300 dark:bg-navy-600 rounded-full" />
            <div className="flex items-center gap-1 mt-1 text-navy-500 dark:text-navy-400 text-xs">
              {sheetState === "collapsed" ? (
                <>
                  <ChevronUp className="w-3 h-3" />
                  <span>Swipe up to see canvas</span>
                </>
              ) : (
                <>
                  <ChevronDown className="w-3 h-3" />
                  <span>Swipe down to minimize</span>
                </>
              )}
            </div>
          </div>

          {/* Collapsed View - Mini Preview */}
          {sheetState === "collapsed" && (
            <div className="flex-shrink-0 px-3 pb-3">
              <div className="flex gap-2 overflow-x-auto">
                {images.slice(0, 5).map((img) => (
                  <button
                    key={img.id}
                    onClick={() => {
                      onSelectImage(img.id);
                      setSheetState("expanded");
                    }}
                    className={`relative flex-shrink-0 w-14 h-14 rounded-lg overflow-hidden border-2 transition-all ${
                      selectedImage?.id === img.id
                        ? "border-amber-500"
                        : "border-transparent"
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
                {images.length > 5 && (
                  <button
                    onClick={() => setSheetState("expanded")}
                    className="flex-shrink-0 w-14 h-14 rounded-lg bg-navy-100 dark:bg-navy-700 flex items-center justify-center text-navy-600 dark:text-navy-300"
                  >
                    <span className="text-xs font-medium">+{images.length - 5}</span>
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Expanded View - Full Canvas */}
          {sheetState === "expanded" && (
            <div className="flex-1 flex flex-col overflow-hidden">
              {/* Close button */}
              <div className="flex-shrink-0 flex justify-end px-4 pb-2">
                <button
                  onClick={() => setSheetState("collapsed")}
                  className="p-2 text-navy-500 hover:text-navy-700 dark:text-navy-400 dark:hover:text-navy-200 hover:bg-navy-100 dark:hover:bg-navy-700 rounded-full transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Main Image */}
              <div className="flex-1 relative flex items-center justify-center px-4 overflow-hidden">
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

                {/* Generating overlay */}
                {isGenerating && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="absolute inset-0 flex items-center justify-center bg-white/80 dark:bg-navy-900/80 backdrop-blur-sm rounded-xl"
                  >
                    <div className="flex flex-col items-center gap-2">
                      <motion.div
                        animate={{ rotate: 360 }}
                        transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                      >
                        <Sparkles className="w-8 h-8 text-amber-500" />
                      </motion.div>
                      <p className="text-sm font-medium text-navy-600 dark:text-navy-300">
                        Generating...
                      </p>
                    </div>
                  </motion.div>
                )}
              </div>

              {/* Thumbnail Gallery */}
              <div className="flex-shrink-0 border-t border-navy-200 dark:border-navy-700 bg-white dark:bg-navy-800 p-3 mt-2">
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
            </div>
          )}
        </motion.div>
      </motion.div>
    </>
  );
}

export default MobileCanvasSheet;
