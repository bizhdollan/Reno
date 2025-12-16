import { motion } from 'framer-motion';
import { FolderOpen, Plus, Clock, CheckCircle2 } from 'lucide-react';
import { Link } from 'react-router-dom';

export default function ProjectsPage() {
  const projects = [
    {
      id: '1',
      title: 'Kitchen Renovation',
      type: 'Kitchen',
      status: 'completed',
      createdAt: '2024-01-15',
      selectedTier: 'mid',
      totalCost: 35000,
    },
  ];

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

        {projects.length === 0 ? (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-center py-16"
          >
            <FolderOpen className="w-16 h-16 text-navy-300 dark:text-navy-600 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-navy-900 dark:text-white mb-2">No projects yet</h3>
            <p className="text-navy-600 dark:text-navy-400 mb-6">Start your first renovation estimate to see it here.</p>
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
            {projects.map((project, idx) => (
              <motion.div
                key={project.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.1 }}
                className="bg-white dark:bg-navy-800 rounded-2xl border border-navy-100 dark:border-navy-700 p-6 hover:shadow-lg transition-shadow"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-semibold text-navy-900 dark:text-white text-lg">{project.title}</h3>
                    <div className="flex items-center gap-4 mt-2 text-sm text-navy-500 dark:text-navy-400">
                      <span className="flex items-center gap-1">
                        <Clock className="w-4 h-4" />
                        {project.createdAt}
                      </span>
                      <span className="px-2 py-0.5 bg-navy-100 dark:bg-navy-700 rounded-full">
                        {project.type}
                      </span>
                    </div>
                  </div>
                  
                  <div className="text-right">
                    <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400 text-sm font-medium">
                      <CheckCircle2 className="w-4 h-4" />
                      Completed
                    </div>
                    <div className="text-2xl font-bold text-navy-900 dark:text-white mt-1">
                      ${project.totalCost.toLocaleString()}
                    </div>
                    <div className="text-xs text-navy-500 dark:text-navy-400 capitalize">
                      {project.selectedTier} tier
                    </div>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}