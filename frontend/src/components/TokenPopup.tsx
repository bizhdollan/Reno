import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Copy, Check, FileText, Globe, Loader2, X } from 'lucide-react';

interface TokenPopupProps {
  token: string;
  email: string;
  onSaveAsDraft: () => Promise<void>;
  onPublishToMarketplace: () => Promise<void>;
  onClose: () => void;
}

export function TokenPopup({
  token,
  email,
  onSaveAsDraft,
  onPublishToMarketplace,
  onClose
}: TokenPopupProps) {
  const [copied, setCopied] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [actionType, setActionType] = useState<'draft' | 'publish' | null>(null);

  const handleCopy = () => {
    navigator.clipboard.writeText(token);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSaveAsDraft = async () => {
    setActionType('draft');
    setIsProcessing(true);
    try {
      await onSaveAsDraft();
      // Parent component will handle closing and navigation
    } catch (error) {
      console.error('Failed to save as draft:', error);
      setIsProcessing(false);
      setActionType(null);
    }
  };

  const handlePublish = async () => {
    setActionType('publish');
    setIsProcessing(true);
    try {
      await onPublishToMarketplace();
      // Parent component will handle closing and navigation
    } catch (error) {
      console.error('Failed to publish:', error);
      setIsProcessing(false);
      setActionType(null);
    }
  };

  const handleClose = async () => {
    // If closed without choosing, default to draft
    if (!isProcessing) {
      setActionType('draft');
      setIsProcessing(true);
      try {
        await onSaveAsDraft();
      } catch (error) {
        console.error('Failed to save as draft on close:', error);
      }
      onClose();
    }
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4">
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          transition={{ duration: 0.2 }}
          className="bg-white dark:bg-navy-800 rounded-2xl shadow-2xl max-w-lg w-full overflow-hidden"
        >
          {/* Header with close button */}
          <div className="relative bg-gradient-to-r from-emerald-500 to-emerald-400 p-6">
            <button
              onClick={handleClose}
              disabled={isProcessing}
              className="absolute top-4 right-4 p-2 hover:bg-white/20 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <X className="w-5 h-5 text-white" />
            </button>

            <div className="text-center">
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: 0.1, type: "spring", stiffness: 200 }}
                className="w-16 h-16 bg-white rounded-full flex items-center justify-center mx-auto mb-4 shadow-lg"
              >
                <Check className="w-8 h-8 text-emerald-600" strokeWidth={3} />
              </motion.div>
              <h2 className="text-2xl font-bold text-white mb-2">
                Project Saved Successfully!
              </h2>
              <p className="text-emerald-50">
                Your renovation estimate is ready
              </p>
            </div>
          </div>

          <div className="p-6 space-y-6">
            {/* Token Display */}
            <div className="bg-gradient-to-r from-amber-500 to-amber-400 rounded-xl p-1">
              <div className="bg-white dark:bg-navy-900 rounded-lg p-6 text-center">
                <p className="text-sm text-navy-600 dark:text-navy-400 mb-2 font-medium">
                  Your Project Code
                </p>
                <div className="font-mono text-2xl md:text-3xl font-bold text-navy-900 dark:text-white tracking-wider mb-4 select-all">
                  {token}
                </div>
                <motion.button
                  onClick={handleCopy}
                  whileTap={{ scale: 0.95 }}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-amber-100 dark:bg-amber-500/20 text-amber-800 dark:text-amber-300 hover:bg-amber-200 dark:hover:bg-amber-500/30 rounded-lg transition-colors font-medium"
                >
                  {copied ? (
                    <>
                      <Check className="w-4 h-4 text-emerald-600" />
                      <span className="text-emerald-600">Copied!</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-4 h-4" />
                      <span>Copy Code</span>
                    </>
                  )}
                </motion.button>
              </div>
            </div>

            {/* Email Confirmation */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="bg-blue-50 dark:bg-blue-500/10 rounded-xl p-4 border border-blue-200 dark:border-blue-500/20"
            >
              <p className="text-sm text-blue-900 dark:text-blue-200 flex items-start gap-2">
                <span className="text-lg">📧</span>
                <span>
                  Code sent to <strong className="break-all">{email}</strong>
                </span>
              </p>
            </motion.div>

            {/* Important Notice */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="bg-amber-50 dark:bg-amber-500/10 rounded-xl p-4 border border-amber-200 dark:border-amber-500/20"
            >
              <p className="text-sm text-amber-900 dark:text-amber-200 flex items-start gap-2">
                <span className="text-lg">💡</span>
                <span>
                  <strong>Save this code!</strong> You'll need it to access and manage your project anytime.
                </span>
              </p>
            </motion.div>

            {/* Divider */}
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-navy-200 dark:border-navy-700"></div>
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-4 bg-white dark:bg-navy-800 text-navy-500 dark:text-navy-400 font-medium">
                  Choose what to do next
                </span>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="grid sm:grid-cols-2 gap-3">
              {/* Save as Draft */}
              <motion.button
                onClick={handleSaveAsDraft}
                disabled={isProcessing}
                whileHover={!isProcessing ? { scale: 1.02 } : {}}
                whileTap={!isProcessing ? { scale: 0.98 } : {}}
                className={`group relative overflow-hidden rounded-xl p-4 border-2 transition-all ${
                  actionType === 'draft' && isProcessing
                    ? 'border-navy-500 bg-navy-50 dark:bg-navy-900/50'
                    : 'border-navy-200 dark:border-navy-700 hover:border-navy-400 dark:hover:border-navy-500 hover:bg-navy-50 dark:hover:bg-navy-900/30'
                } disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                <div className="relative z-10">
                  <div className="flex items-center justify-center mb-2">
                    {isProcessing && actionType === 'draft' ? (
                      <Loader2 className="w-6 h-6 text-navy-600 dark:text-navy-300 animate-spin" />
                    ) : (
                      <FileText className="w-6 h-6 text-navy-600 dark:text-navy-300 group-hover:text-navy-700 dark:group-hover:text-navy-200 transition-colors" />
                    )}
                  </div>
                  <p className="font-semibold text-navy-900 dark:text-white mb-1">
                    Save as Draft
                  </p>
                  <p className="text-xs text-navy-600 dark:text-navy-400">
                    Keep private, edit later
                  </p>
                </div>
                <div className="absolute inset-0 bg-gradient-to-br from-navy-50 to-transparent dark:from-navy-900/50 dark:to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
              </motion.button>

              {/* Publish to Marketplace */}
              <motion.button
                onClick={handlePublish}
                disabled={isProcessing}
                whileHover={!isProcessing ? { scale: 1.02 } : {}}
                whileTap={!isProcessing ? { scale: 0.98 } : {}}
                className={`group relative overflow-hidden rounded-xl p-4 transition-all ${
                  actionType === 'publish' && isProcessing
                    ? 'bg-gradient-to-r from-emerald-600 to-emerald-500'
                    : 'bg-gradient-to-r from-emerald-500 to-emerald-400 hover:from-emerald-600 hover:to-emerald-500'
                } disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-emerald-500/25`}
              >
                <div className="relative z-10">
                  <div className="flex items-center justify-center mb-2">
                    {isProcessing && actionType === 'publish' ? (
                      <Loader2 className="w-6 h-6 text-white animate-spin" />
                    ) : (
                      <Globe className="w-6 h-6 text-white" />
                    )}
                  </div>
                  <p className="font-semibold text-white mb-1">
                    Publish to Marketplace
                  </p>
                  <p className="text-xs text-emerald-50">
                    Find contractors now
                  </p>
                </div>
                <div className="absolute inset-0 bg-gradient-to-br from-white/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
              </motion.button>
            </div>

            {/* Helper Text */}
            <p className="text-center text-xs text-navy-500 dark:text-navy-400">
              {isProcessing
                ? `${actionType === 'draft' ? 'Saving as draft' : 'Publishing to marketplace'}...`
                : 'Closing without choosing will save as draft'
              }
            </p>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
