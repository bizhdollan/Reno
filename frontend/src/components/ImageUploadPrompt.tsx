import { useRef } from "react";
import { motion } from "framer-motion";
import { Upload, Camera, ImageIcon, ArrowRight } from "lucide-react";

interface ImageUploadPromptProps {
  onFileSelect: (files: FileList) => void;
  onCameraClick: () => void;
  projectType?: string;
  isUploading?: boolean;
}

export function ImageUploadPrompt({
  onFileSelect,
  onCameraClick,
  projectType = "room",
  isUploading = false,
}: ImageUploadPromptProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onFileSelect(e.target.files);
      e.target.value = "";
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onFileSelect(e.dataTransfer.files);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="w-full max-w-md mx-auto pt-10"
    >
      <div className="bg-white  dark:bg-navy-800 rounded-2xl border border-navy-200 dark:border-navy-700 shadow-lg overflow-hidden">
        {/* Header */}
        <div className="px-5 py-4 border-b border-navy-100 dark:border-navy-700">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-amber-100 dark:bg-amber-500/20 flex items-center justify-center">
              <ImageIcon className="w-5 h-5 text-amber-600 dark:text-amber-400" />
            </div>
            <div>
              <h3 className="font-semibold text-navy-900 dark:text-white">
                Upload your {projectType} photos
              </h3>
              <p className="text-sm text-navy-500 dark:text-navy-400">
                Share images of the space you want to renovate
              </p>
            </div>
          </div>
        </div>

        {/* Upload Area */}
        <div className="p-5">
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            className="border-2 border-dashed border-navy-200 dark:border-navy-600 rounded-xl p-6 text-center hover:border-amber-400 dark:hover:border-amber-500 transition-colors cursor-pointer bg-navy-50/50 dark:bg-navy-900/50"
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept="image/jpeg,image/png,image/webp"
              onChange={handleFileChange}
              className="hidden"
              disabled={isUploading}
            />

            <motion.div
              animate={{ y: [0, -5, 0] }}
              transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
              className="w-14 h-14 mx-auto mb-4 rounded-full bg-amber-100 dark:bg-amber-500/20 flex items-center justify-center"
            >
              <Upload className="w-7 h-7 text-amber-600 dark:text-amber-400" />
            </motion.div>

            <p className="text-navy-700 dark:text-navy-200 font-medium mb-1">
              Drag & drop images here
            </p>
            <p className="text-sm text-navy-500 dark:text-navy-400 mb-4">
              or click to browse
            </p>

            <motion.button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                fileInputRef.current?.click();
              }}
              disabled={isUploading}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-amber-500 hover:bg-amber-600 text-white font-medium rounded-lg transition-colors disabled:opacity-50"
            >
              <Upload className="w-4 h-4" />
              Choose Files
            </motion.button>
          </div>

          {/* Or use camera */}
          <div className="mt-4 flex items-center gap-3">
            <div className="flex-1 h-px bg-navy-200 dark:bg-navy-700" />
            <span className="text-xs text-navy-400 dark:text-navy-500 uppercase tracking-wide">or</span>
            <div className="flex-1 h-px bg-navy-200 dark:bg-navy-700" />
          </div>

          <motion.button
            type="button"
            onClick={onCameraClick}
            disabled={isUploading}
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.99 }}
            className="mt-4 w-full flex items-center justify-center gap-2 py-3 px-4 bg-navy-100 dark:bg-navy-700 hover:bg-navy-200 dark:hover:bg-navy-600 text-navy-700 dark:text-navy-200 font-medium rounded-xl transition-colors disabled:opacity-50"
          >
            <Camera className="w-5 h-5" />
            Take a Photo
          </motion.button>
        </div>

        {/* Tips */}
        <div className="px-5 pb-5">
          <div className="bg-navy-50 dark:bg-navy-900/50 rounded-lg p-3">
            <p className="text-xs text-navy-500 dark:text-navy-400">
              <span className="font-medium text-navy-600 dark:text-navy-300">Tips:</span>{" "}
              Upload clear, well-lit photos showing the full space. Multiple angles help us provide better estimates.
            </p>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

export default ImageUploadPrompt;
