import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Layout from './components/Layout';
import ErrorBoundary from './components/ErrorBoundary';
import { MatcherProvider } from './contexts/MatcherContext';
import Ingestion from './pages/Ingestion';
import Matcher from './pages/Matcher';
import TaxonomyViewer from './pages/TaxonomyViewer';
import VectorStatus from './pages/VectorStatus';

const queryClient = new QueryClient();

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <MatcherProvider>
          <BrowserRouter>
            <Layout>
              <Routes>
              <Route path="/" element={<Navigate to="/matcher" replace />} />
              <Route path="/ingestion" element={<Ingestion />} />
              <Route path="/matcher" element={<Matcher />} />
              <Route path="/taxonomy" element={<TaxonomyViewer />} />
              <Route path="/vector-status" element={<VectorStatus />} />
              </Routes>
            </Layout>
          </BrowserRouter>
        </MatcherProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;
