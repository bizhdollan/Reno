/**
 * Project Page - View project details by token
 */
import { useParams } from 'react-router-dom';

export default function ProjectPage() {
  const { token } = useParams<{ token: string }>();
  
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-6">
          Your Project
        </h1>
        <p className="text-gray-600 mb-4">
          Project Token: <span className="font-mono font-bold">{token}</span>
        </p>
        {/* TODO: Implement project details view */}
      </div>
    </div>
  );
}

