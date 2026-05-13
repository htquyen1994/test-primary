/**
 * App — Router + Providers
 * Satisfies: Requirements 18.9, 18.10
 */
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AlertsWebSocketProvider } from './providers/AlertsWebSocketProvider'
import { PortfolioWebSocketProvider } from './providers/PortfolioWebSocketProvider'
import { PortfolioHeader } from './components/PortfolioHeader'
import { SignalsPage } from './pages/SignalsPage'
import { JournalPage } from './pages/JournalPage'
import { AnalyticsPage } from './pages/AnalyticsPage'
import { ExchangeConfigPage } from './pages/config/ExchangeConfigPage'
import { TradingParamsPage } from './pages/config/TradingParamsPage'
import { LogPage } from './pages/LogPage'
import { MonitorPage } from './pages/monitor/MonitorPage'
import { HelpPage } from './pages/HelpPage'

export default function App() {
  return (
    <BrowserRouter>
      <AlertsWebSocketProvider>
        <PortfolioWebSocketProvider>
          <div className="min-h-screen bg-gray-950 text-gray-100">
            <PortfolioHeader />
            <main>
              <Routes>
                <Route path="/" element={<SignalsPage />} />
                <Route path="/monitor" element={<MonitorPage />} />
                <Route path="/journal" element={<JournalPage />} />
                <Route path="/analytics" element={<AnalyticsPage />} />
                <Route path="/config/exchange" element={<ExchangeConfigPage />} />
                <Route path="/config/trading" element={<TradingParamsPage />} />
                <Route path="/logs" element={<LogPage />} />
                <Route path="/help" element={<HelpPage />} />
              </Routes>
            </main>
          </div>
        </PortfolioWebSocketProvider>
      </AlertsWebSocketProvider>
    </BrowserRouter>
  )
}
