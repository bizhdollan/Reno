import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Home, MapPin, Loader2, ChevronDown, AlertCircle, CheckCircle2, Navigation, Edit3, X } from "lucide-react";

// Geolocation status types
type GeoStatus = "idle" | "requesting" | "success" | "denied" | "unavailable" | "error";

interface DetectedLocation {
  zipCode: string;
  city: string;
  state: string;
  streetAddress?: string;
  latitude?: number;
  longitude?: number;
  country?: string;
  county?: string;
}

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

interface LocationData {
  zipCode: string;
  city?: string;
  state?: string;
  streetAddress?: string;
  latitude?: number;
  longitude?: number;
  country?: string;
  county?: string;
}

interface ProjectBasicsFormProps {
  onSubmit: (data: {
    projectTitle: string;
    projectType: string;
    zipCode: string;
    streetAddress?: string;
    location?: LocationData;
  }) => void;
  isLoading?: boolean;
  initialData?: {
    projectTitle?: string;
    projectType?: string;
    zipCode?: string;
    streetAddress?: string;
  };
}

export function ProjectBasicsForm({ onSubmit, isLoading = false, initialData }: ProjectBasicsFormProps) {
  const [projectTitle, setProjectTitle] = useState(initialData?.projectTitle || "");
  const [projectType, setProjectType] = useState(initialData?.projectType || "");
  const [customType, setCustomType] = useState("");
  const [zipCode, setZipCode] = useState(initialData?.zipCode || "");
  const [streetAddress, setStreetAddress] = useState(initialData?.streetAddress || "");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [isValidatingZip, setIsValidatingZip] = useState(false);
  const [zipValidated, setZipValidated] = useState(false);
  const [zipLocationInfo, setZipLocationInfo] = useState<string | null>(null);

  // Geolocation state
  const [geoStatus, setGeoStatus] = useState<GeoStatus>("idle");
  const [detectedLocation, setDetectedLocation] = useState<DetectedLocation | null>(null);
  const [locationConfirmed, setLocationConfirmed] = useState(false);
  const [showManualEntry, setShowManualEntry] = useState(false);

  // Reverse geocode coordinates to get address info
  const reverseGeocode = useCallback(async (lat: number, lng: number): Promise<DetectedLocation | null> => {
    try {
      // Using BigDataCloud free reverse geocoding API (no API key required)
      const response = await fetch(
        `https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=${lat}&longitude=${lng}&localityLanguage=en`
      );
      if (!response.ok) {
        return null;
      }

      const data = await response.json();
      // Extract location data - capture as much as possible
      const zipCode = data.postcode || "";
      const city = data.city || data.locality || "";
      const state = data.principalSubdivisionCode?.replace("US-", "") || data.principalSubdivision || "";
      const country = data.countryCode || data.countryName || "";
      const county = data.localityInfo?.administrative?.find((a: any) => a.adminLevel === 6)?.name || "";

      if (!zipCode) {
        return null;
      }

      return {
        zipCode,
        city,
        state,
        country,
        county,
        latitude: lat,
        longitude: lng
      };
    } catch (error) {
      return null;
    }
  }, []);

  // Request geolocation on mount (only if no initial data)
  useEffect(() => {

    if (initialData?.zipCode) {
      setShowManualEntry(true);
      return;
    }

    if (!navigator.geolocation) {
      setGeoStatus("unavailable");
      setShowManualEntry(true);
      return;
    }

    setGeoStatus("requesting");

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        console.log("[Geolocation] SUCCESS - Got position:", {
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracy: position.coords.accuracy
        });

        const { latitude, longitude } = position.coords;
        const location = await reverseGeocode(latitude, longitude);

        if (location && location.zipCode) {
          console.log("[Geolocation] Auto-filling form with:", {
            zipCode: location.zipCode,
            city: location.city,
            state: location.state
          });
          setDetectedLocation(location);
          setGeoStatus("success");
          // Auto-fill the form with detected location
          setZipCode(location.zipCode);
          setZipLocationInfo(`${location.city}, ${location.state}`);
          setZipValidated(true);
          setLocationConfirmed(true);
          setShowManualEntry(true);
        } else {
          setGeoStatus("error");
          setShowManualEntry(true);
        }
      },
      (error) => {
        if (error.code === error.PERMISSION_DENIED) {
          setGeoStatus("denied");
        } else {
          setGeoStatus("error");
        }
        setShowManualEntry(true);
      },
      {
        enableHighAccuracy: false,
        timeout: 10000,
        maximumAge: 300000 // Cache for 5 minutes
      }
    );
  }, [initialData?.zipCode, reverseGeocode]);

  // Handle confirming detected location
  const handleConfirmLocation = useCallback(async () => {
    if (!detectedLocation) return;

    setZipCode(detectedLocation.zipCode);
    setZipLocationInfo(`${detectedLocation.city}, ${detectedLocation.state}`);
    setLocationConfirmed(true);
    setZipValidated(true);
    setShowManualEntry(true);
  }, [detectedLocation]);

  // Handle editing detected location
  const handleEditLocation = useCallback(() => {
    setShowManualEntry(true);
    setLocationConfirmed(false);
    // Pre-fill with detected values if available
    if (detectedLocation) {
      setZipCode(detectedLocation.zipCode);
    }
  }, [detectedLocation]);

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

    // Build comprehensive location data
    const locationData: LocationData = {
      zipCode: zipCode.trim(),
      city: detectedLocation?.city || zipLocationInfo?.split(",")[0]?.trim(),
      state: detectedLocation?.state || zipLocationInfo?.split(",")[1]?.trim(),
      streetAddress: streetAddress.trim() || undefined,
      latitude: detectedLocation?.latitude,
      longitude: detectedLocation?.longitude,
      country: detectedLocation?.country,
      county: detectedLocation?.county,
    };

    onSubmit({
      projectTitle: projectTitle.trim(),
      projectType: finalType.trim(),
      zipCode: zipCode.trim(),
      streetAddress: streetAddress.trim() || undefined,
      location: locationData,
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

          {/* Location Section */}
          <div>
            <label className="block text-sm font-medium text-navy-700 dark:text-navy-300 mb-2">
              Location
            </label>

            <AnimatePresence mode="wait">
              {/* Requesting geolocation state */}
              {geoStatus === "requesting" && (
                <motion.div
                  key="requesting"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="p-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-xl"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-amber-100 dark:bg-amber-800 rounded-lg">
                      <Navigation className="w-5 h-5 text-amber-600 dark:text-amber-400 animate-pulse" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-navy-800 dark:text-navy-200">
                        Detecting your location...
                      </p>
                      <p className="text-xs text-navy-500 dark:text-navy-400">
                        Allow location access for accurate pricing
                      </p>
                    </div>
                    <Loader2 className="w-5 h-5 text-amber-500 animate-spin ml-auto" />
                  </div>
                </motion.div>
              )}

              {/* Detected location - confirmation card */}
              {geoStatus === "success" && detectedLocation && !showManualEntry && (
                <motion.div
                  key="detected"
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  className="p-4 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-700 rounded-xl"
                >
                  <div className="flex items-start gap-3">
                    <div className="p-2 bg-emerald-100 dark:bg-emerald-800 rounded-lg">
                      <MapPin className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                    </div>
                    <div className="flex-1">
                      <p className="text-sm font-medium text-navy-800 dark:text-navy-200">
                        Is this your location?
                      </p>
                      <p className="text-base font-semibold text-navy-900 dark:text-white mt-1">
                        {detectedLocation.city}, {detectedLocation.state} {detectedLocation.zipCode}
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-2 mt-3">
                    <button
                      type="button"
                      onClick={handleConfirmLocation}
                      className="flex-1 py-2 px-4 bg-emerald-500 hover:bg-emerald-600 text-white text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
                    >
                      <CheckCircle2 size={16} />
                      Yes, this is correct
                    </button>
                    <button
                      type="button"
                      onClick={handleEditLocation}
                      className="py-2 px-4 bg-white dark:bg-navy-700 border border-navy-200 dark:border-navy-600 text-navy-700 dark:text-navy-300 text-sm font-medium rounded-lg hover:bg-navy-50 dark:hover:bg-navy-600 transition-colors flex items-center gap-2"
                    >
                      <Edit3 size={16} />
                      Edit
                    </button>
                  </div>
                </motion.div>
              )}

              {/* Manual entry - ZIP Code field */}
              {showManualEntry && (
                <motion.div
                  key="manual"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                >
                  {/* Show confirmed location banner if applicable */}
                  {locationConfirmed && detectedLocation && (
                    <div className="mb-3 p-3 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-700 rounded-lg flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 size={16} className="text-emerald-500" />
                        <span className="text-sm text-navy-700 dark:text-navy-300">
                          {detectedLocation.city}, {detectedLocation.state}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          setLocationConfirmed(false);
                          setZipValidated(false);
                        }}
                        className="p-1 text-navy-400 hover:text-navy-600 dark:hover:text-navy-200"
                      >
                        <X size={14} />
                      </button>
                    </div>
                  )}

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
                        setLocationConfirmed(false);
                      }}
                      onBlur={handleZipBlur}
                      placeholder="Enter ZIP code (e.g., 90210)"
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
                  {zipValidated && zipLocationInfo && !locationConfirmed && (
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
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Street Address (Optional) */}
          <div>
            <label
              htmlFor="streetAddress"
              className="block text-sm font-medium text-navy-700 dark:text-navy-300 mb-2"
            >
              Street Address <span className="text-navy-400 font-normal">(optional)</span>
            </label>
            <div className="relative">
              <Home className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-navy-400" />
              <input
                id="streetAddress"
                type="text"
                value={streetAddress}
                onChange={(e) => setStreetAddress(e.target.value)}
                placeholder="e.g., 123 Main St"
                disabled={isLoading}
                className="w-full pl-10 pr-4 py-3 bg-navy-50 dark:bg-navy-900 border border-navy-200 dark:border-navy-700 rounded-xl text-navy-900 dark:text-white placeholder-navy-400 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent transition-all disabled:opacity-50"
              />
            </div>
            <p className="mt-1.5 text-xs text-navy-400 dark:text-navy-500">
              Enables property-specific insights (NYC addresses get DOB data)
            </p>
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
