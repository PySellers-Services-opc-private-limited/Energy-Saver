import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import DashboardPage from './pages/DashboardPage'
import ForecastPage from './pages/ForecastPage'
import AnomaliesPage from './pages/AnomaliesPage'
import HVACPage from './pages/HVACPage'
import SavingsPage from './pages/SavingsPage'
import ModelsPage from './pages/ModelsPage'
import PipelinePage from './pages/PipelinePage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<DashboardPage />} />
        <Route path="forecast" element={<ForecastPage />} />
        <Route path="anomalies" element={<AnomaliesPage />} />
        <Route path="hvac" element={<HVACPage />} />
        <Route path="savings" element={<SavingsPage />} />
        <Route path="models" element={<ModelsPage />} />
        <Route path="pipeline" element={<PipelinePage />} />
      </Route>
    </Routes>
  )
}
