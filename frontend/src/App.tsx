import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import HomePage from './features/home/HomePage';
import SituationsPage from './features/situations/SituationsPage';
import SituationDetail from './features/situations/SituationDetail';
import ReadinessPage from './features/readiness/ReadinessPage';
import DecisionsPage from './features/decisions/DecisionsPage';
import RoutesPage from './features/routes/RoutesPage';
import ReportsPage from './features/reports/ReportsPage';
import AskMovePage from './features/ask-move/AskMovePage';

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/situations" element={<SituationsPage />} />
        <Route path="/situations/:id" element={<SituationDetail />} />
        <Route path="/readiness" element={<ReadinessPage />} />
        <Route path="/decisions" element={<DecisionsPage />} />
        <Route path="/routes" element={<RoutesPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/ask" element={<AskMovePage />} />
      </Routes>
    </Layout>
  );
}

export default App;
