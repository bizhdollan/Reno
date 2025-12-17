import { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, ZoomIn, ZoomOut, Download } from 'lucide-react';

interface ImageLightboxProps {
  isOpen: boolean;
  imageUrl: string;
  alt?: string;
  onClose: () => void;
}

export default function ImageLightbox({ isOpen, imageUrl, alt = 'Image', onClose }: ImageLightboxProps) {
  // Close on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    
    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    }
    
    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, onClose]);

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-0 z-[100] flex items-center justify-center"
          onClick={onClose}
        >
          {/* Backdrop */}
          <div className="absolute inset-0 bg-black/80 backdrop-blur-md" />
          
          {/* Close button */}
          <motion.button
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
            transition={{ delay: 0.1 }}
            onClick={onClose}
            className="absolute top-4 right-4 z-10 w-10 h-10 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center transition-colors"
            aria-label="Close"
          >
            <X className="w-5 h-5 text-white" />
          </motion.button>

          {/* Image container */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
            className="relative max-w-[90vw] max-h-[85vh] z-10"
            onClick={(e) => e.stopPropagation()}
          >
            <img
              src={imageUrl}
              alt={alt}
              className="max-w-full max-h-[85vh] object-contain rounded-lg shadow-2xl"
            />
            
            {/* Image info bar */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-black/60 to-transparent rounded-b-lg"
            >
              <p className="text-white/80 text-sm truncate">{alt}</p>
            </motion.div>
          </motion.div>

          {/* Click outside hint */}
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
            className="absolute bottom-4 left-1/2 -translate-x-1/2 text-white/50 text-sm"
          >
            Click outside or press ESC to close
          </motion.p>
        </motion.div>
      )}
    </AnimatePresence>
  );
}