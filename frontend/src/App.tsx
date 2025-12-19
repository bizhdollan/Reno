import { Routes, Route } from 'react-router-dom';
import Navbar from './components/shared/Navbar';
import LandingPage from './app/routes/index';
import EstimatePage from './app/routes/EstimatePage';
import MarketplacePage from './app/routes/MarketplacePage';
import ProjectsPage from './app/routes/ProjectsPage';
import UnlockSuccessPage from './app/routes/UnlockSuccessPage';

export default function App() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/estimate" element={<EstimatePage />} />
        <Route path="/marketplace" element={<MarketplacePage />} />
        <Route path="/projects" element={<ProjectsPage />} />
        <Route path="/unlock/success" element={<UnlockSuccessPage />} />
      </Routes>
    </div>
  );
}