import { useState, useCallback, useRef } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

export interface DetectedEntity {
  type: string;
  label: string;
  confidence: number;
}

interface UseEntityDetectionResult {
  entities: DetectedEntity[];
  isLoading: boolean;
  error: string | null;
  detectEntities: (imageUrl: string, projectId?: string) => Promise<void>;
  clearEntities: () => void;
}

// Convert image URL to base64 data URL
async function imageUrlToBase64(url: string): Promise<string> {
  // If already a data URL, return as-is
  if (url.startsWith("data:")) {
    return url;
  }

  try {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Failed to fetch image: ${response.status}`);
    }

    const blob = await response.blob();

    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => {
        if (typeof reader.result === "string") {
          resolve(reader.result);
        } else {
          reject(new Error("Failed to convert to base64"));
        }
      };
      reader.onerror = () => reject(new Error("FileReader error"));
      reader.readAsDataURL(blob);
    });
  } catch (err) {
    console.error("[imageUrlToBase64] Error:", err);
    throw err;
  }
}

export function useEntityDetection(): UseEntityDetectionResult {
  const [entities, setEntities] = useState<DetectedEntity[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Cache to avoid repeated API calls for same image
  const cacheRef = useRef<Map<string, DetectedEntity[]>>(new Map());

  const detectEntities = useCallback(async (imageUrl: string, projectId?: string) => {
    if (!imageUrl) {
      setError("No image URL provided");
      return;
    }

    // Check cache first
    const cacheKey = imageUrl;
    if (cacheRef.current.has(cacheKey)) {
      setEntities(cacheRef.current.get(cacheKey)!);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      // Convert URL to base64 data URL
      const base64Image = await imageUrlToBase64(imageUrl);

      const response = await fetch(`${API_BASE}/detect-entities`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          image_url: base64Image,
          project_id: projectId,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: "Detection failed" }));
        throw new Error(errorData.detail || "Failed to detect entities");
      }

      const data = await response.json();
      const detectedEntities = data.entities || [];

      // Cache the result
      cacheRef.current.set(cacheKey, detectedEntities);
      setEntities(detectedEntities);
    } catch (err) {
      console.error("[useEntityDetection] Error:", err);
      setError(err instanceof Error ? err.message : "Failed to detect entities");
      // Set default entities on error
      const defaultEntities = [
        { type: "floor", label: "Floor", confidence: 0.8 },
        { type: "walls", label: "Walls", confidence: 0.8 },
        { type: "ceiling", label: "Ceiling", confidence: 0.8 },
        { type: "window", label: "Windows", confidence: 0.7 },
      ];
      setEntities(defaultEntities);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const clearEntities = useCallback(() => {
    setEntities([]);
    setError(null);
  }, []);

  return {
    entities,
    isLoading,
    error,
    detectEntities,
    clearEntities,
  };
}

export default useEntityDetection;
