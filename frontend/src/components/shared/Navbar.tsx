import { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Home, 
  FileText, 
  Store, 
  FolderOpen, 
  Menu, 
  X,
  Sun,
  Moon
} from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';

const navItems = [
  { path: '/', label: 'Home', icon: Home },
  { path: '/estimate', label: 'Get Estimate', icon: FileText },
  { path: '/projects', label: 'My Projects', icon: FolderOpen },
  { path: '/marketplace', label: 'Contractors', icon: Store },
];

export default function Navbar() {
  const location = useLocation();
  const { theme, toggleTheme } = useTheme();
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 10);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // Close mobile menu on route change
  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [location.pathname]);

  // Prevent body scroll when mobile menu is open
  useEffect(() => {
    if (isMobileMenuOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [isMobileMenuOpen]);

  return (
    <>
      <nav
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
          isScrolled
            ? 'bg-white/80 dark:bg-navy-950/80 backdrop-blur-lg shadow-sm'
            : 'bg-transparent'
        }`}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16 md:h-20">
            {/* Logo */}
            <Link to="/" className="flex items-center gap-2 group">
              <motion.div
                whileHover={{ rotate: 10, scale: 1.05 }}
                transition={{ type: 'spring', stiffness: 400, damping: 10 }}
                className="w-9 h-9 md:w-10 md:h-10 bg-gradient-to-br from-amber-400 to-amber-500 rounded-xl flex items-center justify-center shadow-lg shadow-amber-500/25"
              >
                <Home className="w-5 h-5 md:w-6 md:h-6 text-white" />
              </motion.div>
              <span className="text-lg md:text-xl font-bold text-navy-900 dark:text-white">
                Renovation<span className="text-amber-500">Tech</span>
              </span>
            </Link>

            {/* Desktop Navigation */}
            <div className="hidden md:flex items-center gap-1">
              {navItems.map((item) => {
                const isActive = location.pathname === item.path;
                const Icon = item.icon;
                
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`relative px-4 py-2 rounded-lg font-medium text-sm transition-all duration-200 flex items-center gap-2 ${
                      isActive
                        ? 'text-amber-600 dark:text-amber-400'
                        : 'text-navy-600 dark:text-navy-200 hover:text-navy-900 dark:hover:text-white hover:bg-navy-100/50 dark:hover:bg-navy-800/50'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    {item.label}
                    {isActive && (
                      <motion.div
                        layoutId="navbar-indicator"
                        className="absolute inset-0 bg-amber-100 dark:bg-amber-500/20 rounded-lg -z-10"
                        transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                      />
                    )}
                  </Link>
                );
              })}
            </div>

            {/* Right Section */}
            <div className="flex items-center gap-2">
              {/* Theme Toggle */}
              <motion.button
                onClick={toggleTheme}
                className="relative w-10 h-10 rounded-xl bg-navy-100 dark:bg-navy-800 flex items-center justify-center overflow-hidden"
                whileTap={{ scale: 0.95 }}
                aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
              >
                <AnimatePresence mode="wait">
                  {theme === 'light' ? (
                    <motion.div
                      key="sun"
                      initial={{ y: -20, opacity: 0, rotate: -90 }}
                      animate={{ y: 0, opacity: 1, rotate: 0 }}
                      exit={{ y: 20, opacity: 0, rotate: 90 }}
                      transition={{ duration: 0.2 }}
                    >
                      <Sun className="w-5 h-5 text-amber-500" />
                    </motion.div>
                  ) : (
                    <motion.div
                      key="moon"
                      initial={{ y: -20, opacity: 0, rotate: 90 }}
                      animate={{ y: 0, opacity: 1, rotate: 0 }}
                      exit={{ y: 20, opacity: 0, rotate: -90 }}
                      transition={{ duration: 0.2 }}
                    >
                      <Moon className="w-5 h-5 text-navy-200" />
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.button>

              {/* Mobile Menu Button */}
              <motion.button
                onClick={() => setIsMobileMenuOpen(true)}
                className="md:hidden w-10 h-10 rounded-xl bg-navy-100 dark:bg-navy-800 flex items-center justify-center"
                whileTap={{ scale: 0.95 }}
                aria-label="Open menu"
              >
                <Menu className="w-5 h-5 text-navy-700 dark:text-navy-200" />
              </motion.button>
            </div>
          </div>
        </div>
      </nav>

      {/* Mobile Menu Drawer */}
      <AnimatePresence>
        {isMobileMenuOpen && (
          <>
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 md:hidden"
              onClick={() => setIsMobileMenuOpen(false)}
            />

            {/* Drawer */}
            <motion.div
              initial={{ x: '100%' }}
              animate={{ x: 0 }}
              exit={{ x: '100%' }}
              transition={{ type: 'spring', damping: 30, stiffness: 300 }}
              className="fixed right-0 top-0 bottom-0 w-72 bg-white dark:bg-navy-900 z-50 md:hidden shadow-2xl"
            >
              {/* Drawer Header */}
              <div className="flex items-center justify-between p-4 border-b border-navy-100 dark:border-navy-800">
                <span className="text-lg font-bold text-navy-900 dark:text-white">Menu</span>
                <motion.button
                  onClick={() => setIsMobileMenuOpen(false)}
                  className="w-10 h-10 rounded-xl bg-navy-100 dark:bg-navy-800 flex items-center justify-center"
                  whileTap={{ scale: 0.95 }}
                  aria-label="Close menu"
                >
                  <X className="w-5 h-5 text-navy-700 dark:text-navy-200" />
                </motion.button>
              </div>

              {/* Drawer Navigation */}
              <div className="p-4 space-y-2">
                {navItems.map((item, index) => {
                  const isActive = location.pathname === item.path;
                  const Icon = item.icon;
                  
                  return (
                    <motion.div
                      key={item.path}
                      initial={{ opacity: 0, x: 20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: index * 0.05 }}
                    >
                      <Link
                        to={item.path}
                        className={`flex items-center gap-3 px-4 py-3 rounded-xl font-medium transition-all ${
                          isActive
                            ? 'bg-amber-100 dark:bg-amber-500/20 text-amber-600 dark:text-amber-400'
                            : 'text-navy-600 dark:text-navy-300 hover:bg-navy-100 dark:hover:bg-navy-800'
                        }`}
                      >
                        <Icon className="w-5 h-5" />
                        {item.label}
                      </Link>
                    </motion.div>
                  );
                })}
              </div>

              {/* Drawer Footer */}
              <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-navy-100 dark:border-navy-800">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-navy-500 dark:text-navy-400">Theme</span>
                  <motion.button
                    onClick={toggleTheme}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg bg-navy-100 dark:bg-navy-800"
                    whileTap={{ scale: 0.95 }}
                  >
                    {theme === 'light' ? (
                      <>
                        <Sun className="w-4 h-4 text-amber-500" />
                        <span className="text-sm text-navy-700 dark:text-navy-200">Light</span>
                      </>
                    ) : (
                      <>
                        <Moon className="w-4 h-4 text-navy-200" />
                        <span className="text-sm text-navy-200">Dark</span>
                      </>
                    )}
                  </motion.button>
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}