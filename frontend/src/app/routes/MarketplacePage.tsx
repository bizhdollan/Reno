import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Search, 
  Filter, 
  MapPin, 
  Clock, 
  Lock, 
  Unlock, 
  X,
  User,
  Mail,
  Phone,
  Home,
  DollarSign,
  ChevronDown,
  RefreshCw,
  Users,
  Eye,
  Sparkles
} from 'lucide-react';

// ==================== TYPES ====================
interface ProjectLead {
  id: string;
  title: string;
  projectType: string;
  zipCode: string;
  createdAt: string;
  tier: 'low' | 'mid' | 'high';
  totalCost: number;
  description: string;
  isUnlocked: boolean;
  thumbnails: string[];
  // Unlocked data
  homeowner?: {
    name: string;
    email: string;
    phone: string;
  };
  details?: {
    materials: string[];
    measurements: { sqft: number; rooms: number };
    timeline: string;
    notes: string;
  };
}

// ==================== MOCK DATA ====================
const MOCK_PROJECTS: ProjectLead[] = [
  {
    id: '1',
    title: 'Modern Kitchen Renovation',
    projectType: 'Kitchen Remodel',
    zipCode: '90210',
    createdAt: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    tier: 'mid',
    totalCost: 42500,
    description: 'Complete kitchen remodel with new cabinets, quartz countertops, and stainless steel appliances. Approximately 200 sq ft kitchen with island.',
    isUnlocked: false,
    thumbnails: [
      'https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=400',
      'https://images.unsplash.com/photo-1556909172-54557c7e4fb7?w=400',
    ],
    homeowner: { name: 'John Smith', email: 'john@email.com', phone: '(555) 123-4567' },
    details: {
      materials: ['Quartz countertops', 'Shaker cabinets', 'Subway tile backsplash', 'Hardwood flooring'],
      measurements: { sqft: 200, rooms: 1 },
      timeline: '4-6 weeks',
      notes: 'Homeowner prefers modern minimalist style. Budget is flexible for quality materials.',
    },
  },
  {
    id: '2',
    title: 'Master Bath Upgrade',
    projectType: 'Bathroom Renovation',
    zipCode: '10001',
    createdAt: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString(),
    tier: 'high',
    totalCost: 28000,
    description: 'Master bathroom renovation with walk-in shower, freestanding tub, and double vanity. High-end fixtures throughout.',
    isUnlocked: false,
    thumbnails: [
      'https://images.unsplash.com/photo-1552321554-5fefe8c9ef14?w=400',
      'https://images.unsplash.com/photo-1620626011761-996317b8d101?w=400',
    ],
    homeowner: { name: 'Sarah Johnson', email: 'sarah@email.com', phone: '(555) 234-5678' },
    details: {
      materials: ['Marble tile', 'Frameless glass shower', 'Freestanding soaking tub', 'Custom vanity'],
      measurements: { sqft: 120, rooms: 1 },
      timeline: '3-4 weeks',
      notes: 'Spa-like atmosphere desired. Water-efficient fixtures preferred.',
    },
  },
  {
    id: '3',
    title: 'Basement Entertainment Room',
    projectType: 'Basement Finishing',
    zipCode: '60601',
    createdAt: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
    tier: 'low',
    totalCost: 24000,
    description: 'Finish 800 sq ft basement as entertainment space. Basic finishes, no bathroom. Some waterproofing needed.',
    isUnlocked: false,
    thumbnails: [
      'https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=400',
    ],
    homeowner: { name: 'Mike Chen', email: 'mike@email.com', phone: '(555) 345-6789' },
    details: {
      materials: ['LVP flooring', 'Drywall', 'Recessed lighting', 'Basic trim'],
      measurements: { sqft: 800, rooms: 1 },
      timeline: '2-3 weeks',
      notes: 'Budget-conscious but wants quality. Planning to add home theater later.',
    },
  },
  {
    id: '4',
    title: 'Open Concept Living Room',
    projectType: 'Room Addition',
    zipCode: '30301',
    createdAt: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(),
    tier: 'mid',
    totalCost: 35000,
    description: 'Remove wall between kitchen and living room to create open concept space. Includes structural beam and flooring updates.',
    isUnlocked: true,
    thumbnails: [
      'https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=400',
      'https://images.unsplash.com/photo-1600566753190-17f0baa2a6c3?w=400',
    ],
    homeowner: { name: 'Emily Davis', email: 'emily@email.com', phone: '(555) 456-7890' },
    details: {
      materials: ['LVL beam', 'Engineered hardwood', 'Recessed lighting', 'Paint'],
      measurements: { sqft: 450, rooms: 2 },
      timeline: '2-3 weeks',
      notes: 'Permit already pulled. Ready to start ASAP.',
    },
  },
  {
    id: '5',
    title: 'Deck & Patio Installation',
    projectType: 'Deck/Patio',
    zipCode: '85001',
    createdAt: new Date(Date.now() - 4 * 24 * 60 * 60 * 1000).toISOString(),
    tier: 'mid',
    totalCost: 18500,
    description: 'New composite deck with pergola and stone patio area. Includes outdoor lighting and basic landscaping.',
    isUnlocked: false,
    thumbnails: [
      'https://images.unsplash.com/photo-1600566752355-35792bedcfea?w=400',
    ],
    homeowner: { name: 'Robert Wilson', email: 'robert@email.com', phone: '(555) 567-8901' },
    details: {
      materials: ['Composite decking', 'Cedar pergola', 'Flagstone patio', 'LED lighting'],
      measurements: { sqft: 350, rooms: 1 },
      timeline: '1-2 weeks',
      notes: 'Backyard entertaining space. HOA approval obtained.',
    },
  },
  {
    id: '6',
    title: 'Hardwood Floor Refinishing',
    projectType: 'Flooring',
    zipCode: '02101',
    createdAt: new Date(Date.now() - 6 * 24 * 60 * 60 * 1000).toISOString(),
    tier: 'low',
    totalCost: 4800,
    description: 'Sand and refinish existing hardwood floors throughout main level. Approximately 1200 sq ft.',
    isUnlocked: false,
    thumbnails: [
      'https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=400',
    ],
    homeowner: { name: 'Lisa Brown', email: 'lisa@email.com', phone: '(555) 678-9012' },
    details: {
      materials: ['Water-based polyurethane', 'Wood filler', 'Stain (natural)'],
      measurements: { sqft: 1200, rooms: 4 },
      timeline: '3-4 days',
      notes: 'Prefer low-VOC products. Will vacate during work.',
    },
  },
];

const PROJECT_TYPES = [
  'All Project Types',
  'Kitchen Remodel',
  'Bathroom Renovation',
  'Basement Finishing',
  'Room Addition',
  'Deck/Patio',
  'Flooring',
];

// ==================== UTILITIES ====================
function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(amount);
}

function formatTimeAgo(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffHours / 24);
  
  if (diffHours < 1) return 'just now';
  if (diffHours < 24) return `about ${diffHours} hour${diffHours === 1 ? '' : 's'} ago`;
  if (diffDays === 1) return '1 day ago';
  return `${diffDays} days ago`;
}

// ==================== COMPONENTS ====================
const tierConfig = {
  low: { label: 'Low Tier', color: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-400' },
  mid: { label: 'Mid Tier', color: 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400' },
  high: { label: 'High Tier', color: 'bg-purple-100 text-purple-700 dark:bg-purple-500/20 dark:text-purple-400' },
};

interface ProjectCardProps {
  project: ProjectLead;
  onUnlock: (project: ProjectLead) => void;
  onView: (project: ProjectLead) => void;
}

function ProjectCard({ project, onUnlock, onView }: ProjectCardProps) {
  const tier = tierConfig[project.tier];
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -4 }}
      className="bg-white dark:bg-navy-800 rounded-2xl border border-navy-100 dark:border-navy-700 overflow-hidden shadow-sm hover:shadow-xl transition-all duration-300"
    >
      {/* Thumbnails */}
      <div className="relative h-40 bg-navy-100 dark:bg-navy-900 overflow-hidden">
        {project.thumbnails.length > 0 ? (
          <div className="flex h-full">
            {project.thumbnails.slice(0, 2).map((thumb, idx) => (
              <img 
                key={idx} 
                src={thumb} 
                alt={`Project ${idx + 1}`} 
                className={`h-full object-cover ${project.thumbnails.length > 1 ? 'w-1/2' : 'w-full'}`}
              />
            ))}
          </div>
        ) : (
          <div className="h-full flex items-center justify-center">
            <Home className="w-12 h-12 text-navy-300 dark:text-navy-600" />
          </div>
        )}
        
        {/* Status badge */}
        <div className={`absolute top-3 right-3 flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${
          project.isUnlocked 
            ? 'bg-emerald-500 text-white' 
            : 'bg-white/90 dark:bg-navy-800/90 text-navy-700 dark:text-navy-200'
        }`}>
          {project.isUnlocked ? <Unlock className="w-3 h-3" /> : <Lock className="w-3 h-3" />}
          {project.isUnlocked ? 'Unlocked' : 'Locked'}
        </div>
      </div>
      
      {/* Content */}
      <div className="p-5">
        <div className="flex items-start justify-between mb-2">
          <h3 className="font-semibold text-navy-900 dark:text-white text-lg leading-tight">{project.title}</h3>
        </div>
        
        <div className="flex items-center gap-3 text-sm text-navy-500 dark:text-navy-400 mb-3">
          <span className="flex items-center gap-1">
            <MapPin className="w-3.5 h-3.5" />
            {project.zipCode}
          </span>
          <span className="flex items-center gap-1">
            <Clock className="w-3.5 h-3.5" />
            {formatTimeAgo(project.createdAt)}
          </span>
        </div>
        
        <div className="flex items-center gap-2 mb-4">
          <span className="px-2.5 py-1 bg-navy-100 dark:bg-navy-700 text-navy-700 dark:text-navy-300 text-xs font-medium rounded-full">
            {project.projectType}
          </span>
          <span className={`px-2.5 py-1 text-xs font-medium rounded-full ${tier.color}`}>
            {tier.label}
          </span>
        </div>
        
        <div className="flex items-baseline gap-1 mb-3">
          <DollarSign className="w-4 h-4 text-amber-500" />
          <span className="text-2xl font-bold text-navy-900 dark:text-white">{formatCurrency(project.totalCost)}</span>
        </div>
        
        <p className="text-sm text-navy-600 dark:text-navy-300 mb-4 line-clamp-2">{project.description}</p>
        
        {/* Locked/Unlocked content */}
        {project.isUnlocked ? (
          <div className="p-3 bg-emerald-50 dark:bg-emerald-500/10 rounded-xl mb-4 border border-emerald-200 dark:border-emerald-500/20">
            <h4 className="font-medium text-sm text-navy-900 dark:text-white flex items-center gap-2 mb-2">
              <User className="w-4 h-4" />
              Homeowner Contact
            </h4>
            <div className="space-y-1 text-sm">
              <p className="flex items-center gap-2 text-navy-700 dark:text-navy-300">
                <User className="w-3.5 h-3.5 text-navy-400" />
                {project.homeowner?.name}
              </p>
              <p className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
                <Mail className="w-3.5 h-3.5" />
                {project.homeowner?.email}
              </p>
              <p className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
                <Phone className="w-3.5 h-3.5" />
                {project.homeowner?.phone}
              </p>
            </div>
          </div>
        ) : (
          <div className="p-3 bg-navy-50 dark:bg-navy-900/50 rounded-xl mb-4 border border-navy-200 dark:border-navy-700">
            <p className="text-sm text-navy-500 dark:text-navy-400 flex items-center gap-2">
              <Lock className="w-4 h-4" />
              Full scope & contact hidden
            </p>
          </div>
        )}
        
        {/* Action button */}
        {project.isUnlocked ? (
          <motion.button
            onClick={() => onView(project)}
            whileTap={{ scale: 0.98 }}
            className="w-full py-3 bg-emerald-500 hover:bg-emerald-600 text-white font-medium rounded-xl transition-colors flex items-center justify-center gap-2"
          >
            <Eye className="w-4 h-4" />
            Contact Homeowner
          </motion.button>
        ) : (
          <motion.button
            onClick={() => onUnlock(project)}
            whileTap={{ scale: 0.98 }}
            className="w-full py-3 bg-gradient-to-r from-amber-500 to-amber-400 hover:from-amber-600 hover:to-amber-500 text-navy-900 font-medium rounded-xl transition-all shadow-lg shadow-amber-500/25 hover:shadow-xl hover:shadow-amber-500/30 flex items-center justify-center gap-2"
          >
            <Unlock className="w-4 h-4" />
            Unlock Full Scope — $199
          </motion.button>
        )}
      </div>
    </motion.div>
  );
}

// ==================== UNLOCK MODAL ====================
interface UnlockModalProps {
  project: ProjectLead | null;
  onClose: () => void;
  onConfirm: (project: ProjectLead) => void;
}

function UnlockModal({ project, onClose, onConfirm }: UnlockModalProps) {
  if (!project) return null;
  
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 20 }}
        onClick={(e) => e.stopPropagation()}
        className="relative bg-white dark:bg-navy-800 rounded-2xl shadow-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto"
      >
        {/* Header */}
        <div className="sticky top-0 bg-white dark:bg-navy-800 border-b border-navy-100 dark:border-navy-700 px-6 py-4 flex items-center justify-between">
          <h2 className="text-xl font-bold text-navy-900 dark:text-white">Unlock Full Scope</h2>
          <button onClick={onClose} className="p-2 hover:bg-navy-100 dark:hover:bg-navy-700 rounded-lg transition-colors">
            <X className="w-5 h-5 text-navy-500" />
          </button>
        </div>
        
        {/* Content */}
        <div className="p-6">
          {/* Project Summary */}
          <div className="bg-navy-50 dark:bg-navy-900/50 rounded-xl p-4 mb-6">
            <h3 className="font-semibold text-navy-900 dark:text-white mb-2">{project.title}</h3>
            <div className="flex items-center gap-4 text-sm text-navy-600 dark:text-navy-400">
              <span className="flex items-center gap-1"><MapPin className="w-4 h-4" />{project.zipCode}</span>
              <span className="flex items-center gap-1"><DollarSign className="w-4 h-4" />{formatCurrency(project.totalCost)}</span>
            </div>
          </div>
          
          {/* What you'll get */}
          <h4 className="font-medium text-navy-900 dark:text-white mb-3">What you'll get:</h4>
          <ul className="space-y-3 mb-6">
            {[
              'Homeowner contact information (name, email, phone)',
              'Detailed project scope and requirements',
              'Material specifications and preferences',
              'Project timeline and availability',
              'Additional notes and special requests',
            ].map((item, idx) => (
              <li key={idx} className="flex items-start gap-3 text-sm text-navy-600 dark:text-navy-300">
                <Sparkles className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />
                {item}
              </li>
            ))}
          </ul>
          
          {/* Price */}
          <div className="bg-gradient-to-br from-amber-50 to-amber-100 dark:from-amber-500/10 dark:to-amber-500/5 rounded-xl p-4 mb-6 border border-amber-200 dark:border-amber-500/20">
            <div className="flex items-center justify-between">
              <span className="text-navy-700 dark:text-navy-300">Unlock fee</span>
              <span className="text-2xl font-bold text-navy-900 dark:text-white">$199</span>
            </div>
            <p className="text-xs text-navy-500 dark:text-navy-400 mt-1">One-time payment, full access forever</p>
          </div>
          
          {/* Action buttons */}
          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="flex-1 py-3 px-4 bg-navy-100 dark:bg-navy-700 text-navy-700 dark:text-navy-200 font-medium rounded-xl hover:bg-navy-200 dark:hover:bg-navy-600 transition-colors"
            >
              Cancel
            </button>
            <motion.button
              onClick={() => onConfirm(project)}
              whileTap={{ scale: 0.98 }}
              className="flex-1 py-3 px-4 bg-gradient-to-r from-amber-500 to-amber-400 text-navy-900 font-semibold rounded-xl shadow-lg shadow-amber-500/25"
            >
              Confirm & Pay
            </motion.button>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}

// ==================== VIEW MODAL ====================
interface ViewModalProps {
  project: ProjectLead | null;
  onClose: () => void;
}

function ViewModal({ project, onClose }: ViewModalProps) {
  if (!project) return null;
  
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 20 }}
        onClick={(e) => e.stopPropagation()}
        className="relative bg-white dark:bg-navy-800 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto"
      >
        {/* Header */}
        <div className="sticky top-0 bg-white dark:bg-navy-800 border-b border-navy-100 dark:border-navy-700 px-6 py-4 flex items-center justify-between z-10">
          <h2 className="text-xl font-bold text-navy-900 dark:text-white">{project.title}</h2>
          <button onClick={onClose} className="p-2 hover:bg-navy-100 dark:hover:bg-navy-700 rounded-lg transition-colors">
            <X className="w-5 h-5 text-navy-500" />
          </button>
        </div>
        
        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Images */}
          {project.thumbnails.length > 0 && (
            <div className="flex gap-2 overflow-x-auto pb-2">
              {project.thumbnails.map((thumb, idx) => (
                <img key={idx} src={thumb} alt={`Project ${idx + 1}`} className="h-40 rounded-xl object-cover flex-shrink-0" />
              ))}
            </div>
          )}
          
          {/* Project Info */}
          <div className="grid sm:grid-cols-2 gap-4">
            <div className="bg-navy-50 dark:bg-navy-900/50 rounded-xl p-4">
              <h4 className="text-sm font-medium text-navy-500 dark:text-navy-400 mb-1">Project Type</h4>
              <p className="font-medium text-navy-900 dark:text-white">{project.projectType}</p>
            </div>
            <div className="bg-navy-50 dark:bg-navy-900/50 rounded-xl p-4">
              <h4 className="text-sm font-medium text-navy-500 dark:text-navy-400 mb-1">Budget</h4>
              <p className="font-medium text-navy-900 dark:text-white">{formatCurrency(project.totalCost)}</p>
            </div>
            <div className="bg-navy-50 dark:bg-navy-900/50 rounded-xl p-4">
              <h4 className="text-sm font-medium text-navy-500 dark:text-navy-400 mb-1">Location</h4>
              <p className="font-medium text-navy-900 dark:text-white">{project.zipCode}</p>
            </div>
            <div className="bg-navy-50 dark:bg-navy-900/50 rounded-xl p-4">
              <h4 className="text-sm font-medium text-navy-500 dark:text-navy-400 mb-1">Timeline</h4>
              <p className="font-medium text-navy-900 dark:text-white">{project.details?.timeline || 'TBD'}</p>
            </div>
          </div>
          
          {/* Description */}
          <div>
            <h4 className="font-medium text-navy-900 dark:text-white mb-2">Description</h4>
            <p className="text-navy-600 dark:text-navy-300">{project.description}</p>
          </div>
          
          {/* Materials */}
          {project.details?.materials && (
            <div>
              <h4 className="font-medium text-navy-900 dark:text-white mb-2">Materials & Specifications</h4>
              <div className="flex flex-wrap gap-2">
                {project.details.materials.map((material, idx) => (
                  <span key={idx} className="px-3 py-1.5 bg-navy-100 dark:bg-navy-700 text-navy-700 dark:text-navy-300 text-sm rounded-lg">
                    {material}
                  </span>
                ))}
              </div>
            </div>
          )}
          
          {/* Notes */}
          {project.details?.notes && (
            <div>
              <h4 className="font-medium text-navy-900 dark:text-white mb-2">Additional Notes</h4>
              <p className="text-navy-600 dark:text-navy-300 text-sm">{project.details.notes}</p>
            </div>
          )}
          
          {/* Homeowner Contact */}
          <div className="bg-emerald-50 dark:bg-emerald-500/10 rounded-xl p-5 border border-emerald-200 dark:border-emerald-500/20">
            <h4 className="font-medium text-navy-900 dark:text-white flex items-center gap-2 mb-4">
              <User className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
              Homeowner Contact
            </h4>
            <div className="space-y-3">
              <p className="flex items-center gap-3 text-navy-700 dark:text-navy-300">
                <User className="w-4 h-4 text-navy-400" />
                <span className="font-medium">{project.homeowner?.name}</span>
              </p>
              <a href={`mailto:${project.homeowner?.email}`} className="flex items-center gap-3 text-amber-600 dark:text-amber-400 hover:underline">
                <Mail className="w-4 h-4" />
                {project.homeowner?.email}
              </a>
              <a href={`tel:${project.homeowner?.phone}`} className="flex items-center gap-3 text-amber-600 dark:text-amber-400 hover:underline">
                <Phone className="w-4 h-4" />
                {project.homeowner?.phone}
              </a>
            </div>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}

// ==================== MAIN COMPONENT ====================
export default function MarketplacePage() {
  const [projects, setProjects] = useState<ProjectLead[]>(MOCK_PROJECTS);
  const [searchZip, setSearchZip] = useState('');
  const [selectedType, setSelectedType] = useState('All Project Types');
  const [unlockingProject, setUnlockingProject] = useState<ProjectLead | null>(null);
  const [viewingProject, setViewingProject] = useState<ProjectLead | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  
  const filteredProjects = useMemo(() => {
    return projects.filter(p => {
      const matchesZip = !searchZip || p.zipCode.includes(searchZip);
      const matchesType = selectedType === 'All Project Types' || p.projectType === selectedType;
      return matchesZip && matchesType;
    });
  }, [projects, searchZip, selectedType]);
  
  const activeLeads = projects.filter(p => !p.isUnlocked).length;
  
  const handleRefresh = () => {
    setIsRefreshing(true);
    setTimeout(() => setIsRefreshing(false), 1000);
  };
  
  const handleUnlock = (project: ProjectLead) => {
    setUnlockingProject(project);
  };
  
  const handleConfirmUnlock = (project: ProjectLead) => {
    setProjects(prev => prev.map(p => p.id === project.id ? { ...p, isUnlocked: true } : p));
    setUnlockingProject(null);
  };
  
  const handleView = (project: ProjectLead) => {
    setViewingProject(project);
  };
  
  return (
    <div className="min-h-screen bg-gradient-to-b from-navy-50 to-white dark:from-navy-950 dark:to-navy-900 pt-20 md:pt-24">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-8">
          <div>
            <h1 className="text-3xl font-bold text-navy-900 dark:text-white">Contractor Marketplace</h1>
            <p className="text-navy-600 dark:text-navy-400 mt-1">Browse pre-scoped renovation leads in your area</p>
          </div>
          
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 px-4 py-2 bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-400 rounded-xl">
              <Users className="w-4 h-4" />
              <span className="text-sm font-medium">{activeLeads} Active Leads</span>
            </div>
            <motion.button
              onClick={handleRefresh}
              whileTap={{ scale: 0.95 }}
              className="flex items-center gap-2 px-4 py-2 bg-white dark:bg-navy-800 border border-navy-200 dark:border-navy-700 text-navy-700 dark:text-navy-200 rounded-xl hover:bg-navy-50 dark:hover:bg-navy-700 transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
              <span className="text-sm font-medium">Refresh</span>
            </motion.button>
          </div>
        </div>
        
        {/* Filters */}
        <div className="bg-white dark:bg-navy-800 rounded-2xl border border-navy-100 dark:border-navy-700 p-4 mb-8">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="flex items-center gap-2 text-navy-500 dark:text-navy-400">
              <Filter className="w-4 h-4" />
              <span className="text-sm font-medium">Filters:</span>
            </div>
            
            {/* ZIP Search */}
            <div className="relative flex-1 max-w-xs">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-navy-400" />
              <input
                type="text"
                placeholder="Search by ZIP code..."
                value={searchZip}
                onChange={(e) => setSearchZip(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 bg-navy-50 dark:bg-navy-900 border border-navy-200 dark:border-navy-700 rounded-xl text-sm text-navy-900 dark:text-white placeholder-navy-400 focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>
            
            {/* Project Type */}
            <div className="relative">
              <select
                value={selectedType}
                onChange={(e) => setSelectedType(e.target.value)}
                className="appearance-none px-4 py-2.5 pr-10 bg-navy-50 dark:bg-navy-900 border border-navy-200 dark:border-navy-700 rounded-xl text-sm text-navy-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-amber-500 cursor-pointer"
              >
                {PROJECT_TYPES.map(type => (
                  <option key={type} value={type}>{type}</option>
                ))}
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-navy-400 pointer-events-none" />
            </div>
          </div>
        </div>
        
        {/* Projects Grid */}
        {filteredProjects.length === 0 ? (
          <div className="text-center py-16">
            <Home className="w-16 h-16 text-navy-300 dark:text-navy-600 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-navy-900 dark:text-white mb-2">No projects found</h3>
            <p className="text-navy-600 dark:text-navy-400">Try adjusting your filters or check back later for new leads.</p>
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredProjects.map((project, idx) => (
              <motion.div
                key={project.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.05 }}
              >
                <ProjectCard project={project} onUnlock={handleUnlock} onView={handleView} />
              </motion.div>
            ))}
          </div>
        )}
        
        {/* How It Works */}
        <div className="mt-16 bg-white dark:bg-navy-800 rounded-2xl border border-navy-100 dark:border-navy-700 p-8">
          <h2 className="text-2xl font-bold text-navy-900 dark:text-white mb-8">How It Works for Contractors</h2>
          <div className="grid md:grid-cols-3 gap-8">
            {[
              { num: 1, title: 'Browse Leads', desc: 'View pre-scoped projects with accepted pricing tiers' },
              { num: 2, title: 'Unlock Full Scope', desc: 'Pay $199 to access detailed scope and homeowner contact' },
              { num: 3, title: 'Win the Job', desc: 'Contact the homeowner directly and submit your bid' },
            ].map((step) => (
              <div key={step.num} className="text-center">
                <div className="w-12 h-12 bg-gradient-to-br from-amber-400 to-amber-500 rounded-full flex items-center justify-center text-white font-bold text-xl mx-auto mb-4 shadow-lg shadow-amber-500/25">
                  {step.num}
                </div>
                <h3 className="font-semibold text-navy-900 dark:text-white mb-2">{step.title}</h3>
                <p className="text-sm text-navy-600 dark:text-navy-400">{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
      
      {/* Modals */}
      <AnimatePresence>
        {unlockingProject && (
          <UnlockModal project={unlockingProject} onClose={() => setUnlockingProject(null)} onConfirm={handleConfirmUnlock} />
        )}
        {viewingProject && (
          <ViewModal project={viewingProject} onClose={() => setViewingProject(null)} />
        )}
      </AnimatePresence>
    </div>
  );
}