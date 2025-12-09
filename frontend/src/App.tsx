import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Route components
import LandingPage from './app/routes/index';
import EstimatePage from './app/routes/EstimatePage';
import MarketplacePage from './app/routes/MarketplacePage';
import ProjectPage from './app/routes/ProjectPage';

// Create TanStack Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      refetchOnWindowFocus: false,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/estimate" element={<EstimatePage />} />
          <Route path="/marketplace" element={<MarketplacePage />} />
          <Route path="/projects/:token" element={<ProjectPage />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
