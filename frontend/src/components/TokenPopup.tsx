import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface TokenPopupProps {
  token: string;
  email: string;
  onClose: () => void;
}

export function TokenPopup({ token, email, onClose }: TokenPopupProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(token);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm px-4">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.9 }}
          className="bg-white dark:bg-navy-800 rounded-2xl shadow-2xl max-w-md w-full p-6 md:p-8"
        >
          {/* Header */}
          <div className="text-center mb-6">
            <div className="w-16 h-16 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-green-600 dark:text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h2 className="text-2xl font-bold text-navy-900 dark:text-white">
              Project Saved!
            </h2>
            <p className="text-navy-600 dark:text-navy-300 mt-2">
              Your renovation estimate has been saved
            </p>
          </div>

          {/* Token Display */}
          <div className="bg-gradient-to-r from-amber-500 to-amber-400 rounded-xl p-1 mb-6">
            <div className="bg-white dark:bg-navy-900 rounded-lg p-6 text-center">
              <p className="text-sm text-navy-600 dark:text-navy-300 mb-2">
                Your Project Code
              </p>
              <div className="font-mono text-2xl md:text-3xl font-bold text-navy-900 dark:text-white tracking-wider mb-4 break-all">
                {token}
              </div>
              <button
                onClick={handleCopy}
                className="inline-flex items-center gap-2 px-4 py-2 bg-amber-100 dark:bg-amber-500/20 text-amber-800 dark:text-amber-200 hover:bg-amber-200 dark:hover:bg-amber-500/30 rounded-lg transition-colors"
              >
                {copied ? (
                  <>
                    <svg className="w-5 h-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    <span className="text-green-600">Copied!</span>
                  </>
                ) : (
                  <>
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                    <span>Copy Code</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Email Confirmation */}
          <div className="bg-amber-50 dark:bg-amber-500/10 rounded-lg p-4 mb-6">
            <p className="text-sm text-amber-900 dark:text-amber-200">
              📧 Code sent to: <strong className="break-all">{email}</strong>
            </p>
          </div>

          {/* Info */}
          <div className="bg-navy-50 dark:bg-navy-900/50 rounded-lg p-4 mb-6">
            <p className="text-sm text-navy-700 dark:text-navy-300">
              💡 <strong>Save this code!</strong> You'll need it to access your project anytime.
            </p>
          </div>

          {/* Actions */}
          <div className="flex flex-col sm:flex-row gap-3">
            <button
              onClick={onClose}
              className="flex-1 px-6 py-3 bg-gradient-to-r from-amber-500 to-amber-400 text-navy-900 rounded-lg font-medium hover:opacity-90 transition-opacity"
            >
              Continue
            </button>
            <a
              href={`/projects?token=${token}`}
              className="flex-1 px-6 py-3 border-2 border-navy-200 dark:border-navy-700 text-navy-700 dark:text-navy-200 rounded-lg font-medium text-center hover:bg-navy-50 dark:hover:bg-navy-900 transition-colors"
            >
              View Project
            </a>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
