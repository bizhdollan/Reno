import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FolderOpen, Plus, Clock, CheckCircle2, Search, Loader2, Copy, CheckCircle, KeyRound, User, Globe, Mail, Phone, X, Eye } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../../lib/api';

interface Project {
  id: string;
  token: string;
  projectType: string | null;
  status: string;
  createdAt: string;
  totalCost: number | null;
  zipCode: string | null;
  isUnlock?: boolean;
  contractorEmail?: string | null;
  // Homeowner contact
  homeownerName?: string | null;
  homeownerEmail?: string | null;
  homeownerPhone?: string | null;
  // Project details
  briefScope?: string | null;
}

export default function ProjectsPage() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [tokenInput, setTokenInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [tokenCopied, setTokenCopied] = useState(false);
  const [publishingProject, setPublishingProject] = useState<Project | null>(null);
  const [publishForm, setPublishForm] = useState({
    homeownerName: '',
    homeownerEmail: '',
    homeownerPhone: '',
  });
  const [isPublishing, setIsPublishing] = useState(false);

  const normalizeToken = (token: string) => token.trim().toUpperCase();

  const getTokenType = (token: string): 'project' | 'unlock' | 'invalid' => {
    if (/^PRJ-[A-Z0-9]{6}$/.test(token)) return 'project';
    if (/^UNL-[A-Z0-9]{6}$/.test(token)) return 'unlock';
    return 'invalid';
  };

  const loadProject = useCallback(async (token: string) => {
    const normalized = normalizeToken(token);
    if (!normalized) return;

    const type = getTokenType(normalized);
    if (type === 'invalid') {
      setError('Token format not recognized. Use PRJ-XXXXXX or UNL-XXXXXX.');
      return;
    }
    
    setIsLoading(true);
    setError(null);
    
    try {
      let mappedProject: Project;

      if (type === 'project') {
        const project = await api.getProjectByToken(normalized);

        // Debug: Log the project response to see what we're getting
        console.log('📦 Project fetched from backend:', project);
        console.log('👤 Homeowner details:', {
          name: project.homeowner_name,
          email: project.homeowner_email,
          phone: project.homeowner_phone
        });

        mappedProject = {
          id: project.id,
          token: project.token,
          projectType: project.project_type || null,
          status: project.status,
          createdAt: project.created_at,
          totalCost: project.total_price ? parseFloat(project.total_price) : null,
          zipCode: project.zip_code || null,
          isUnlock: false,
          homeownerName: project.homeowner_name || null,
          homeownerEmail: project.homeowner_email || null,
          homeownerPhone: project.homeowner_phone || null,
        };
      } else {
        // UNL unlock token
        const unlock = await api.getUnlockDetails(normalized);
        const project = unlock.project;
        mappedProject = {
          id: project.id,
          token: unlock.unlock_token,
          projectType: project.project_type || null,
          status: project.status,
          createdAt: project.created_at,
          totalCost: project.total_price ? parseFloat(project.total_price) : null,
          zipCode: project.zip_code || null,
          isUnlock: true,
          contractorEmail: unlock.contractor_email || null,
          // Extract homeowner contact from project
          homeownerName: project.homeowner_name || null,
          homeownerEmail: project.homeowner_email || null,
          homeownerPhone: project.homeowner_phone || null,
          briefScope: project.brief_scope || null,
        };
      }

      // Check if project already exists
      setProjects(prev => {
        if (prev.find(p => p.token === mappedProject.token)) {
          return prev;
        }
        return [...prev, mappedProject];
      });
      setTokenInput('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load project');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const handleLoadProject = () => {
    if (tokenInput.trim()) {
      loadProject(tokenInput.trim());
    }
  };

  const handleCopyToken = (token: string) => {
    navigator.clipboard.writeText(token);
    setTokenCopied(true);
    setTimeout(() => setTokenCopied(false), 2000);
  };

  function formatCurrency(amount: number | null): string {
    if (!amount) return 'N/A';
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(amount);
  }

  const handlePublishClick = (project: Project) => {
    // Debug: Log what we're checking
    console.log('🔍 Checking if project has homeowner details:', {
      name: project.homeownerName,
      email: project.homeownerEmail,
      phone: project.homeownerPhone,
      hasAll: !!(project.homeownerName && project.homeownerEmail && project.homeownerPhone)
    });

    // Check if project already has homeowner details
    if (project.homeownerName && project.homeownerEmail && project.homeownerPhone) {
      console.log('✅ All details present, publishing directly!');
      // Directly publish without showing the form
      handlePublishDirect(project);
    } else {
      console.log('❌ Missing details, showing form. Missing:', {
        name: !project.homeownerName,
        email: !project.homeownerEmail,
        phone: !project.homeownerPhone
      });
      // Show form to collect missing details
      setPublishingProject(project);
    }
  };

  const handlePublishDirect = async (project: Project) => {
    setIsPublishing(true);
    setError(null);
    setSuccessMessage(null);

    try {
      await api.publishProject(
        project.token,
        project.homeownerName!,
        project.homeownerEmail!,
        project.homeownerPhone!
      );

      // Update project status in the list
      setProjects(prev => prev.map(p =>
        p.token === project.token
          ? { ...p, status: 'published' }
          : p
      ));

      // Show success message
      setSuccessMessage('Project published to marketplace successfully!');
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to publish project');
    } finally {
      setIsPublishing(false);
    }
  };

  const handlePublish = async () => {
    if (!publishingProject) return;

    if (!publishForm.homeownerName.trim() || !publishForm.homeownerEmail.trim() || !publishForm.homeownerPhone.trim()) {
      setError('Please fill in all contact details');
      return;
    }

    setIsPublishing(true);
    setError(null);
    setSuccessMessage(null);

    try {
      await api.publishProject(
        publishingProject.token,
        publishForm.homeownerName,
        publishForm.homeownerEmail,
        publishForm.homeownerPhone
      );

      // Update project status in the list
      setProjects(prev => prev.map(p =>
        p.token === publishingProject.token
          ? { ...p, status: 'published', homeownerName: publishForm.homeownerName, homeownerEmail: publishForm.homeownerEmail, homeownerPhone: publishForm.homeownerPhone }
          : p
      ));

      setPublishingProject(null);
      setPublishForm({ homeownerName: '', homeownerEmail: '', homeownerPhone: '' });

      // Show success message
      setSuccessMessage('Project published to marketplace successfully!');
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to publish project');
    } finally {
      setIsPublishing(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-navy-50 to-white dark:from-navy-950 dark:to-navy-900 pt-20 md:pt-24">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-navy-900 dark:text-white">My Projects</h1>
            <p className="text-navy-600 dark:text-navy-400 mt-1">Track your renovation estimates</p>
          </div>
          
          <Link to="/estimate">
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-amber-500 to-amber-400 text-navy-900 font-medium rounded-xl shadow-lg shadow-amber-500/25"
            >
              <Plus className="w-4 h-4" />
              New Estimate
            </motion.button>
          </Link>
        </div>

        {/* Token Input */}
        <div className="bg-white dark:bg-navy-800 rounded-2xl border border-navy-100 dark:border-navy-700 p-6 mb-8">
          <h2 className="text-lg font-semibold text-navy-900 dark:text-white mb-4">Load Project by Token</h2>
          <div className="flex gap-3">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-navy-400" />
              <input
                type="text"
                value={tokenInput}
                onChange={(e) => setTokenInput(e.target.value)}
                placeholder="Enter token (PRJ-XXXXXX for homeowner, UNL-XXXXXX for contractor)"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !isLoading) {
                    handleLoadProject();
                  }
                }}
                className="w-full pl-10 pr-4 py-3 bg-navy-50 dark:bg-navy-900 border border-navy-200 dark:border-navy-700 rounded-xl text-navy-900 dark:text-white placeholder-navy-400 focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>
            <motion.button
              onClick={handleLoadProject}
              disabled={isLoading || !tokenInput.trim()}
              whileTap={{ scale: 0.98 }}
              className="px-6 py-3 bg-gradient-to-r from-amber-500 to-amber-400 text-navy-900 font-semibold rounded-xl shadow-lg shadow-amber-500/25 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Loading...
                </>
              ) : (
                'Load'
              )}
            </motion.button>
          </div>
          {error && (
            <div className="mt-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl">
              <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
            </div>
          )}
          {successMessage && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="mt-4 p-3 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 rounded-xl"
            >
              <p className="text-sm text-emerald-600 dark:text-emerald-400 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4" />
                {successMessage}
              </p>
            </motion.div>
          )}
        </div>

        {projects.length === 0 ? (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-center py-16"
          >
            <FolderOpen className="w-16 h-16 text-navy-300 dark:text-navy-600 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-navy-900 dark:text-white mb-2">No projects loaded</h3>
            <p className="text-navy-600 dark:text-navy-400 mb-6">Enter your project token above to view your projects, or start a new estimate.</p>
            <Link to="/estimate">
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-amber-500 to-amber-400 text-navy-900 font-semibold rounded-xl shadow-lg shadow-amber-500/25"
              >
                <Plus className="w-5 h-5" />
                Get Your First Estimate
              </motion.button>
            </Link>
          </motion.div>
        ) : (
          <div className="space-y-4">
            <AnimatePresence>
              {projects.map((project, idx) => (
                <motion.div
                  key={project.token}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  transition={{ delay: idx * 0.1 }}
                  className="bg-white dark:bg-navy-800 rounded-2xl border border-navy-100 dark:border-navy-700 p-6 hover:shadow-lg transition-shadow"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <h3 className="font-semibold text-navy-900 dark:text-white text-lg">
                          {project.projectType || 'Project'}
                        </h3>
                        <span className="px-2 py-0.5 bg-navy-100 dark:bg-navy-700 rounded-full text-xs text-navy-600 dark:text-navy-300">
                          {project.status}
                        </span>
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
                          project.isUnlock
                            ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300'
                            : 'bg-blue-50 text-blue-700 dark:bg-blue-500/10 dark:text-blue-300'
                        }`}>
                          {project.isUnlock ? 'Unlocked Lead (Contractor)' : 'Homeowner Project'}
                        </span>
                      </div>
                      <div className="flex items-center gap-4 mt-2 text-sm text-navy-500 dark:text-navy-400">
                        <span className="flex items-center gap-1">
                          <Clock className="w-4 h-4" />
                          {new Date(project.createdAt).toLocaleDateString()}
                        </span>
                        {project.zipCode && (
                          <span className="px-2 py-0.5 bg-navy-100 dark:bg-navy-700 rounded-full">
                            {project.zipCode}
                          </span>
                        )}
                      </div>
                      <div className="mt-3 flex items-center gap-2">
                        <code className="text-xs font-mono bg-navy-50 dark:bg-navy-900 px-2 py-1 rounded text-navy-600 dark:text-navy-300">
                          {project.token}
                        </code>
                        <motion.button
                          onClick={() => handleCopyToken(project.token)}
                          whileTap={{ scale: 0.95 }}
                          className="p-1 hover:bg-navy-100 dark:hover:bg-navy-700 rounded transition-colors"
                          title="Copy token"
                        >
                          {tokenCopied ? (
                            <CheckCircle className="w-4 h-4 text-emerald-600" />
                          ) : (
                            <Copy className="w-4 h-4 text-navy-400" />
                          )}
                        </motion.button>
                      </div>
                    </div>
                    
                    <div className="text-right ml-4 space-y-1">
                      {project.totalCost ? (
                        <div className="text-2xl font-bold text-navy-900 dark:text-white">
                          {formatCurrency(project.totalCost)}
                        </div>
                      ) : (
                        <div className="text-sm text-navy-500 dark:text-navy-400">No price set</div>
                      )}
                      {project.isUnlock && project.contractorEmail && (
                        <div className="text-[11px] text-navy-500 dark:text-navy-400 flex items-center justify-end gap-1">
                          <User className="w-3 h-3" />
                          <span>{project.contractorEmail}</span>
                        </div>
                      )}
                    </div>
                  </div>
                  
                  {/* View details button */}
                  <div className="mt-4 pt-4 border-t border-navy-100 dark:border-navy-700">
                    <motion.button
                      onClick={() => navigate(`/projects/${project.token}`)}
                      whileTap={{ scale: 0.98 }}
                      className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-navy-900 dark:bg-navy-700 text-white font-medium rounded-xl hover:bg-navy-800 dark:hover:bg-navy-600 transition-all"
                    >
                      <Eye className="w-4 h-4" />
                      {project.isUnlock ? 'View Full Project & Homeowner Details' : 'View Project Details'}
                    </motion.button>
                  </div>
                  
                  {/* Publish button for draft/completed homeowner projects */}
                  {!project.isUnlock && (project.status === 'completed' || project.status === 'draft') && (
                    <div className="mt-4 pt-4 border-t border-navy-100 dark:border-navy-700">
                      <motion.button
                        onClick={() => handlePublishClick(project)}
                        disabled={isPublishing}
                        whileTap={{ scale: 0.98 }}
                        className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-gradient-to-r from-emerald-500 to-emerald-400 text-white font-medium rounded-xl shadow-lg shadow-emerald-500/25 hover:shadow-xl hover:shadow-emerald-500/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {isPublishing ? (
                          <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            Publishing...
                          </>
                        ) : (
                          <>
                            <Globe className="w-4 h-4" />
                            Publish to Marketplace
                          </>
                        )}
                      </motion.button>
                    </div>
                  )}
                  
                  {/* Published badge */}
                  {!project.isUnlock && project.status === 'published' && (
                    <div className="mt-4 pt-4 border-t border-navy-100 dark:border-navy-700">
                      <div className="flex items-center justify-center gap-2 px-4 py-2 bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 rounded-xl">
                        <Globe className="w-4 h-4" />
                        <span className="text-sm font-medium">Published to Marketplace</span>
                      </div>
                    </div>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}

        {/* Publish Modal */}
        <AnimatePresence>
          {publishingProject && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-50 flex items-center justify-center p-4"
              onClick={() => !isPublishing && setPublishingProject(null)}
            >
              <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
              <motion.div
                initial={{ opacity: 0, scale: 0.95, y: 20 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95, y: 20 }}
                onClick={(e) => e.stopPropagation()}
                className="relative bg-white dark:bg-navy-800 rounded-2xl shadow-2xl max-w-md w-full"
              >
                <div className="p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-xl font-bold text-navy-900 dark:text-white">Publish to Marketplace</h2>
                    {!isPublishing && (
                      <button
                        onClick={() => setPublishingProject(null)}
                        className="p-2 hover:bg-navy-100 dark:hover:bg-navy-700 rounded-lg transition-colors"
                      >
                        <X className="w-5 h-5 text-navy-500" />
                      </button>
                    )}
                  </div>
                  
                  <p className="text-sm text-navy-600 dark:text-navy-400 mb-6">
                    Add your contact details so contractors can reach you after unlocking your project.
                  </p>
                  
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-navy-700 dark:text-navy-300 mb-2">
                        <User className="w-4 h-4 inline mr-1" />
                        Your Name
                      </label>
                      <input
                        type="text"
                        value={publishForm.homeownerName}
                        onChange={(e) => setPublishForm({ ...publishForm, homeownerName: e.target.value })}
                        placeholder="John Doe"
                        disabled={isPublishing}
                        className="w-full px-4 py-3 bg-navy-50 dark:bg-navy-900 border border-navy-200 dark:border-navy-700 rounded-xl text-navy-900 dark:text-white placeholder-navy-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:opacity-50"
                      />
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium text-navy-700 dark:text-navy-300 mb-2">
                        <Mail className="w-4 h-4 inline mr-1" />
                        Email Address
                      </label>
                      <input
                        type="email"
                        value={publishForm.homeownerEmail}
                        onChange={(e) => setPublishForm({ ...publishForm, homeownerEmail: e.target.value })}
                        placeholder="your@email.com"
                        disabled={isPublishing}
                        className="w-full px-4 py-3 bg-navy-50 dark:bg-navy-900 border border-navy-200 dark:border-navy-700 rounded-xl text-navy-900 dark:text-white placeholder-navy-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:opacity-50"
                      />
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium text-navy-700 dark:text-navy-300 mb-2">
                        <Phone className="w-4 h-4 inline mr-1" />
                        Phone Number
                      </label>
                      <input
                        type="tel"
                        value={publishForm.homeownerPhone}
                        onChange={(e) => setPublishForm({ ...publishForm, homeownerPhone: e.target.value })}
                        placeholder="(555) 123-4567"
                        disabled={isPublishing}
                        className="w-full px-4 py-3 bg-navy-50 dark:bg-navy-900 border border-navy-200 dark:border-navy-700 rounded-xl text-navy-900 dark:text-white placeholder-navy-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:opacity-50"
                      />
                    </div>
                  </div>
                  
                  {error && (
                    <div className="mt-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl">
                      <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
                    </div>
                  )}
                  
                  <div className="flex gap-3 mt-6">
                    <button
                      onClick={() => setPublishingProject(null)}
                      disabled={isPublishing}
                      className="flex-1 py-3 px-4 bg-navy-100 dark:bg-navy-700 text-navy-700 dark:text-navy-200 font-medium rounded-xl hover:bg-navy-200 dark:hover:bg-navy-600 transition-colors disabled:opacity-50"
                    >
                      Cancel
                    </button>
                    <motion.button
                      onClick={handlePublish}
                      disabled={isPublishing || !publishForm.homeownerName.trim() || !publishForm.homeownerEmail.trim() || !publishForm.homeownerPhone.trim()}
                      whileTap={{ scale: 0.98 }}
                      className="flex-1 py-3 px-4 bg-gradient-to-r from-emerald-500 to-emerald-400 text-white font-semibold rounded-xl shadow-lg shadow-emerald-500/25 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                      {isPublishing ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          Publishing...
                        </>
                      ) : (
                        <>
                          <Globe className="w-4 h-4" />
                          Publish
                        </>
                      )}
                    </motion.button>
                  </div>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>

      </div>
    </div>
  );
}