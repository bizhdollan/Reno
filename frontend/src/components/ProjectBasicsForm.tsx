import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { Home, MapPin, Loader2, ChevronDown, AlertCircle, CheckCircle2 } from "lucide-react";

// Common project types for renovation
const PROJECT_TYPES = [
  { value: "kitchen", label: "Kitchen" },
  { value: "bathroom", label: "Bathroom" },
  { value: "bedroom", label: "Bedroom" },
  { value: "living room", label: "Living Room" },
  { value: "basement", label: "Basement" },
  { value: "garage", label: "Garage" },
  { value: "outdoor", label: "Outdoor / Patio" },
  { value: "full home", label: "Full Home" },
  { value: "other", label: "Other" },
];

interface ProjectBasicsFormProps {
  onSubmit: (data: { projectTitle: string; projectType: string; zipCode: string }) => void;
  isLoading?: boolean;
  initialData?: {
    projectTitle?: string;
    projectType?: string;
    zipCode?: string;
  };
}

export function ProjectBasicsForm({ onSubmit, isLoading = false, initialData }: ProjectBasicsFormProps) {
  const [projectTitle, setProjectTitle] = useState(initialData?.projectTitle || "");
  const [projectType, setProjectType] = useState(initialData?.projectType || "");
  const [customType, setCustomType] = useState("");
  const [zipCode, setZipCode] = useState(initialData?.zipCode || "");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [isValidatingZip, setIsValidatingZip] = useState(false);
  const [zipValidated, setZipValidated] = useState(false);
  const [zipLocationInfo, setZipLocationInfo] = useState<string | null>(null);

  // If initial projectType doesn't match predefined options, set it as custom
  useEffect(() => {
    if (initialData?.projectType) {
      const matchingType = PROJECT_TYPES.find(t => t.value === initialData.projectType);
      if (!matchingType) {
        setProjectType("other");
        setCustomType(initialData.projectType);
      }
    }
  }, [initialData?.projectType]);

  // Basic format validation (5 digits)
  const isValidZipFormat = (zip: string): boolean => {
    return /^\d{5}$/.test(zip);
  };

  // Async ZIP validation against API
  const validateZipWithAPI = useCallback(async (zip: string): Promise<{ valid: boolean; location?: string; error?: string }> => {
    if (!isValidZipFormat(zip)) {
      return { valid: false, error: "Please enter a valid 5-digit US ZIP code" };
    }

    try {
      const response = await fetch(`https://api.zippopotam.us/us/${zip}`);
      if (!response.ok) {
        if (response.status === 404) {
          return { valid: false, error: "This ZIP code doesn't exist. Please check and try again." };
        }
        return { valid: false, error: "Unable to verify ZIP code. Please try again." };
      }

      const data = await response.json();
      const place = data.places?.[0];
      const location = place ? `${place["place name"]}, ${place["state abbreviation"]}` : undefined;
      return { valid: true, location };
    } catch {
      // Network error - allow submission but warn
      return { valid: true, location: undefined };
    }
  }, []);

  // Validate ZIP on blur
  const handleZipBlur = useCallback(async () => {
    setTouched(prev => ({ ...prev, zipCode: true }));

    if (!zipCode.trim()) {
      setErrors(prev => ({ ...prev, zipCode: "ZIP code is required" }));
      setZipValidated(false);
      setZipLocationInfo(null);
      return;
    }

    if (!isValidZipFormat(zipCode)) {
      setErrors(prev => ({ ...prev, zipCode: "Please enter a valid 5-digit US ZIP code" }));
      setZipValidated(false);
      setZipLocationInfo(null);
      return;
    }

    setIsValidatingZip(true);
    const result = await validateZipWithAPI(zipCode);
    setIsValidatingZip(false);

    if (result.valid) {
      setErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors.zipCode;
        return newErrors;
      });
      setZipValidated(true);
      setZipLocationInfo(result.location || null);
    } else {
      setErrors(prev => ({ ...prev, zipCode: result.error || "Invalid ZIP code" }));
      setZipValidated(false);
      setZipLocationInfo(null);
    }
  }, [zipCode, validateZipWithAPI]);

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!projectTitle.trim()) {
      newErrors.projectTitle = "Project title is required";
    }

    if (!projectType) {
      newErrors.projectType = "Please select a project type";
    } else if (projectType === "other" && !customType.trim()) {
      newErrors.customType = "Please specify the project type";
    }

    if (!zipCode.trim()) {
      newErrors.zipCode = "ZIP code is required";
    } else if (!isValidZipFormat(zipCode)) {
      newErrors.zipCode = "Please enter a valid 5-digit US ZIP code";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Mark all fields as touched
    setTouched({ projectTitle: true, projectType: true, zipCode: true, customType: true });

    // First validate the basic form
    if (!validateForm()) {
      return;
    }

    // If ZIP hasn't been validated yet, validate it now
    if (!zipValidated && isValidZipFormat(zipCode)) {
      setIsValidatingZip(true);
      const result = await validateZipWithAPI(zipCode);
      setIsValidatingZip(false);

      if (!result.valid) {
        setErrors(prev => ({ ...prev, zipCode: result.error || "Invalid ZIP code" }));
        return;
      }
      setZipValidated(true);
      setZipLocationInfo(result.location || null);
    }

    const finalType = projectType === "other" ? customType : projectType;
    onSubmit({
      projectTitle: projectTitle.trim(),
      projectType: finalType.trim(),
      zipCode: zipCode.trim(),
    });
  };

  const handleBlur = (field: string) => {
    setTouched(prev => ({ ...prev, [field]: true }));
    validateForm();
  };

  const showError = (field: string) => touched[field] && errors[field];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="w-full max-w-lg mx-auto"
    >
      <div className="bg-white dark:bg-navy-800 rounded-2xl shadow-xl border border-navy-100 dark:border-navy-700 overflow-hidden">
        {/* Header */}
        <div className="px-6 py-5 border-b border-navy-100 dark:border-navy-700">
          <h2 className="text-xl font-bold text-navy-900 dark:text-white">
            Tell us about your project
          </h2>
          <p className="text-sm text-navy-500 dark:text-navy-400 mt-1">
            We'll use this information to provide accurate estimates
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {/* Project Title */}
          <div>
            <label
              htmlFor="projectTitle"
              className="block text-sm font-medium text-navy-700 dark:text-navy-300 mb-2"
            >
              Project Title
            </label>
            <div className="relative">
              <input
                id="projectTitle"
                type="text"
                value={projectTitle}
                onChange={(e) => setProjectTitle(e.target.value)}
                onBlur={() => handleBlur("projectTitle")}
                placeholder="e.g., Modern Kitchen Renovation"
                disabled={isLoading}
                className={`w-full px-4 py-3 bg-navy-50 dark:bg-navy-900 border rounded-xl text-navy-900 dark:text-white placeholder-navy-400 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent transition-all disabled:opacity-50 ${
                  showError("projectTitle")
                    ? "border-red-400 dark:border-red-500"
                    : "border-navy-200 dark:border-navy-700"
                }`}
              />
            </div>
            {showError("projectTitle") && (
              <motion.p
                initial={{ opacity: 0, y: -5 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-1.5 text-sm text-red-500 dark:text-red-400 flex items-center gap-1"
              >
                <AlertCircle size={14} />
                {errors.projectTitle}
              </motion.p>
            )}
          </div>

          {/* Project Type */}
          <div>
            <label
              htmlFor="projectType"
              className="block text-sm font-medium text-navy-700 dark:text-navy-300 mb-2"
            >
              Project Type
            </label>
            <div className="relative">
              <Home className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-navy-400 pointer-events-none" />
              <select
                id="projectType"
                value={projectType}
                onChange={(e) => {
                  setProjectType(e.target.value);
                  if (e.target.value !== "other") {
                    setCustomType("");
                  }
                }}
                onBlur={() => handleBlur("projectType")}
                disabled={isLoading}
                className={`w-full pl-10 pr-10 py-3 bg-navy-50 dark:bg-navy-900 border rounded-xl text-navy-900 dark:text-white appearance-none focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent transition-all disabled:opacity-50 cursor-pointer ${
                  showError("projectType")
                    ? "border-red-400 dark:border-red-500"
                    : "border-navy-200 dark:border-navy-700"
                } ${!projectType ? "text-navy-400" : ""}`}
              >
                <option value="" disabled>Select a project type</option>
                {PROJECT_TYPES.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-navy-400 pointer-events-none" />
            </div>
            {showError("projectType") && (
              <motion.p
                initial={{ opacity: 0, y: -5 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-1.5 text-sm text-red-500 dark:text-red-400 flex items-center gap-1"
              >
                <AlertCircle size={14} />
                {errors.projectType}
              </motion.p>
            )}

            {/* Custom type input when "Other" is selected */}
            {projectType === "other" && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-3"
              >
                <input
                  type="text"
                  value={customType}
                  onChange={(e) => setCustomType(e.target.value)}
                  onBlur={() => handleBlur("customType")}
                  placeholder="Specify your project type"
                  disabled={isLoading}
                  className={`w-full px-4 py-3 bg-navy-50 dark:bg-navy-900 border rounded-xl text-navy-900 dark:text-white placeholder-navy-400 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent transition-all disabled:opacity-50 ${
                    showError("customType")
                      ? "border-red-400 dark:border-red-500"
                      : "border-navy-200 dark:border-navy-700"
                  }`}
                />
                {showError("customType") && (
                  <motion.p
                    initial={{ opacity: 0, y: -5 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mt-1.5 text-sm text-red-500 dark:text-red-400 flex items-center gap-1"
                  >
                    <AlertCircle size={14} />
                    {errors.customType}
                  </motion.p>
                )}
              </motion.div>
            )}
          </div>

          {/* ZIP Code */}
          <div>
            <label
              htmlFor="zipCode"
              className="block text-sm font-medium text-navy-700 dark:text-navy-300 mb-2"
            >
              ZIP Code
            </label>
            <div className="relative">
              <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-navy-400" />
              <input
                id="zipCode"
                type="text"
                value={zipCode}
                onChange={(e) => {
                  // Only allow digits, max 5
                  const value = e.target.value.replace(/\D/g, "").slice(0, 5);
                  setZipCode(value);
                  // Reset validation state when ZIP changes
                  setZipValidated(false);
                  setZipLocationInfo(null);
                }}
                onBlur={handleZipBlur}
                placeholder="e.g., 90210"
                disabled={isLoading || isValidatingZip}
                maxLength={5}
                inputMode="numeric"
                className={`w-full pl-10 pr-10 py-3 bg-navy-50 dark:bg-navy-900 border rounded-xl text-navy-900 dark:text-white placeholder-navy-400 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent transition-all disabled:opacity-50 ${
                  showError("zipCode")
                    ? "border-red-400 dark:border-red-500"
                    : zipValidated
                    ? "border-emerald-400 dark:border-emerald-500"
                    : "border-navy-200 dark:border-navy-700"
                }`}
              />
              {/* Validation status indicator */}
              <div className="absolute right-3 top-1/2 -translate-y-1/2">
                {isValidatingZip && (
                  <Loader2 className="w-5 h-5 text-amber-500 animate-spin" />
                )}
                {!isValidatingZip && zipValidated && (
                  <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                )}
              </div>
            </div>
            {/* Show location info when validated */}
            {zipValidated && zipLocationInfo && (
              <motion.p
                initial={{ opacity: 0, y: -5 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-1.5 text-xs text-emerald-600 dark:text-emerald-400 flex items-center gap-1"
              >
                <CheckCircle2 size={12} />
                {zipLocationInfo}
              </motion.p>
            )}
            {!zipValidated && !showError("zipCode") && (
              <p className="mt-1.5 text-xs text-navy-400 dark:text-navy-500">
                Used for regional pricing adjustments
              </p>
            )}
            {showError("zipCode") && (
              <motion.p
                initial={{ opacity: 0, y: -5 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-1 text-sm text-red-500 dark:text-red-400 flex items-center gap-1"
              >
                <AlertCircle size={14} />
                {errors.zipCode}
              </motion.p>
            )}
          </div>

          {/* Submit Button */}
          <motion.button
            type="submit"
            disabled={isLoading || isValidatingZip}
            whileHover={{ scale: (isLoading || isValidatingZip) ? 1 : 1.01 }}
            whileTap={{ scale: (isLoading || isValidatingZip) ? 1 : 0.98 }}
            className="w-full py-3.5 px-6 bg-gradient-to-r from-amber-500 to-amber-400 text-navy-900 font-semibold rounded-xl shadow-lg shadow-amber-500/25 hover:shadow-xl hover:shadow-amber-500/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {isLoading || isValidatingZip ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                <span>{isValidatingZip ? "Validating ZIP..." : "Starting..."}</span>
              </>
            ) : (
              <span>Continue</span>
            )}
          </motion.button>
        </form>
      </div>
    </motion.div>
  );
}

export default ProjectBasicsForm;
