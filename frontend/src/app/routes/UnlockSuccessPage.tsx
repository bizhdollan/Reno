import { useEffect, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { CheckCircle2, ArrowRight, Home, Store, Loader2, KeyRound } from 'lucide-react';
import { api } from '../../lib/api';

export default function UnlockSuccessPage() {
  const [params] = useSearchParams();
  const sessionId = params.get('session_id') || params.get('unlock_token');
  const [unlockToken, setUnlockToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // If we have a Stripe session_id, look up the unlock details
    if (!sessionId) return;

    // If we're in mock mode and got an unlock_token directly, just show it
    if (sessionId.startsWith('UNL-')) {
      setUnlockToken(sessionId);
      return;
    }

    setIsLoading(true);
    setError(null);

    api.getUnlockBySession(sessionId)
      .then((data: any) => {
        if (data?.unlock_token) {
          setUnlockToken(data.unlock_token);
        } else {
          setError('Could not find unlock details for this payment.');
        }
      })
      .catch(() => {
        setError('Could not load unlock details. Please check your email for the unlock code.');
      })
      .finally(() => setIsLoading(false));
  }, [sessionId]);

  return (
    <div className="min-h-screen bg-gradient-to-b from-emerald-50 to-white dark:from-emerald-950 dark:to-navy-900 pt-20 md:pt-24">
      <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white dark:bg-navy-800 rounded-3xl shadow-xl border border-emerald-100 dark:border-emerald-800 px-6 sm:px-10 py-10 text-center"
        >
          <div className="flex justify-center mb-6">
            <div className="w-16 h-16 rounded-full bg-emerald-100 dark:bg-emerald-500/10 flex items-center justify-center">
              <CheckCircle2 className="w-10 h-10 text-emerald-600 dark:text-emerald-400" />
            </div>
          </div>

          <h1 className="text-2xl sm:text-3xl font-bold text-navy-900 dark:text-white mb-3">
            Payment Successful
          </h1>

          <p className="text-sm sm:text-base text-navy-600 dark:text-navy-300 mb-4">
            Thank you for unlocking this project. We’ll send a confirmation email with your unlock
            details. You can also use the unlock code below to view the project later.
          </p>

          {/* Unlock token section */}
          <div className="mb-6">
            {isLoading ? (
              <div className="flex items-center justify-center gap-2 text-sm text-navy-500 dark:text-navy-300">
                <Loader2 className="w-4 h-4 animate-spin" />
                Loading unlock details...
              </div>
            ) : unlockToken ? (
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/30">
                <KeyRound className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                <span className="text-xs sm:text-sm font-mono font-semibold text-navy-900 dark:text-white">
                  {unlockToken}
                </span>
              </div>
            ) : error ? (
              <p className="text-xs text-red-600 dark:text-red-400">{error}</p>
            ) : (
              <p className="text-xs text-navy-500 dark:text-navy-400">
                Unlock code will be sent to your email shortly.
              </p>
            )}
          </div>

          {sessionId && (
            <p className="text-xs text-navy-400 dark:text-navy-500 mb-6">
              Reference ID:{' '}
              <code className="px-2 py-1 rounded bg-navy-50 dark:bg-navy-900 text-[10px] sm:text-xs">
                {sessionId}
              </code>
            </p>
          )}

          <div className="grid sm:grid-cols-2 gap-3 mt-4">
            <Link to="/marketplace">
              <motion.button
                whileTap={{ scale: 0.97 }}
                className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-gradient-to-r from-amber-500 to-amber-400 text-navy-900 font-semibold shadow-lg shadow-amber-500/25"
              >
                <Store className="w-4 h-4" />
                Back to Marketplace
                <ArrowRight className="w-4 h-4" />
              </motion.button>
            </Link>

            <Link to="/">
              <motion.button
                whileTap={{ scale: 0.97 }}
                className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-navy-100 dark:bg-navy-800 text-navy-800 dark:text-navy-100 font-medium border border-navy-200 dark:border-navy-700"
              >
                <Home className="w-4 h-4" />
                Go to Home
              </motion.button>
            </Link>
          </div>
        </motion.div>
      </div>
    </div>
  );
}


