/**
 * ExchangeConfigPage — Group B settings
 * Exchange selection, API credentials, assets, position sizing.
 * API keys are masked in display and only sent when changed.
 *
 * Satisfies: Exchange config requirements
 */
import { useEffect, useState } from 'react'
import type { ExchangeSettings, SupportedExchange, AssetConfig } from '../../types/config'

const TIMEFRAMES = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '1d']
const SIZING_MODES = [
  { value: 'fixed_usd', label: 'Fixed USD per trade' },
  { value: 'risk_pct', label: 'Risk % of account' },
  { value: 'kelly', label: 'Kelly Criterion' },
]

export function ExchangeConfigPage() {
  const [settings, setSettings] = useState<ExchangeSettings | null>(null)
  const [exchanges, setExchanges] = useState<SupportedExchange[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<string | null>(null)
  const [saveMsg, setSaveMsg] = useState<string | null>(null)
  const [newAsset, setNewAsset] = useState('')

  useEffect(() => {
    Promise.all([
      fetch('/api/config/exchange').then(r => r.json()),
      fetch('/api/config/exchanges').then(r => r.json()),
    ]).then(([s, e]) => {
      setSettings(s)
      setExchanges(e.exchanges || [])
      setLoading(false)
    })
  }, [])

  const selectedExchange = exchanges.find(e => e.id === settings?.exchange_id)

  async function handleSave() {
    if (!settings) return
    setSaving(true)
    setSaveMsg(null)
    try {
      const res = await fetch('/api/config/exchange', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      })
      const data = await res.json()
      if (res.ok) {
        setSaveMsg(`✓ Saved. Exchange: ${data.exchange} | Testnet: ${data.testnet}`)
        if (data.warning) setSaveMsg(prev => prev + `\n⚠ ${data.warning}`)
      } else {
        setSaveMsg(`✗ Error: ${data.detail}`)
      }
    } catch (err) {
      setSaveMsg(`✗ Network error`)
    } finally {
      setSaving(false)
    }
  }

  async function handleTestConnection() {
    setTesting(true)
    setTestResult(null)
    try {
      const res = await fetch('/api/config/exchange/test-connection')
      const data = await res.json()
      if (res.ok) {
        setTestResult(`✓ Connected to ${data.exchange} | Markets: ${data.markets_count}`)
      } else {
        setTestResult(`✗ ${data.detail}`)
      }
    } catch {
      setTestResult('✗ Connection failed')
    } finally {
      setTesting(false)
    }
  }

  function addAsset() {
    if (!newAsset.trim() || !settings) return
    const symbol = newAsset.trim().toUpperCase()
    if (settings.assets.find(a => a.symbol === symbol)) return
    setSettings({ ...settings, assets: [...settings.assets, { symbol, enabled: true }] })
    setNewAsset('')
  }

  function removeAsset(symbol: string) {
    if (!settings) return
    setSettings({ ...settings, assets: settings.assets.filter(a => a.symbol !== symbol) })
  }

  function updateAsset(symbol: string, updates: Partial<AssetConfig>) {
    if (!settings) return
    setSettings({
      ...settings,
      assets: settings.assets.map(a => a.symbol === symbol ? { ...a, ...updates } : a),
    })
  }

  if (loading || !settings) {
    return <div className="text-center py-12 text-gray-500">Loading exchange settings...</div>
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-white">Exchange Settings</h1>
        <div className="flex gap-2">
          <button
            onClick={handleTestConnection}
            disabled={testing}
            className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-sm text-gray-200 rounded-lg transition-colors disabled:opacity-50"
          >
            {testing ? 'Testing...' : 'Test Connection'}
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-1.5 bg-green-600 hover:bg-green-500 text-sm text-white font-semibold rounded-lg transition-colors disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
      </div>

      {testResult && (
        <div className={`text-sm px-3 py-2 rounded-lg ${testResult.startsWith('✓') ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}`}>
          {testResult}
        </div>
      )}
      {saveMsg && (
        <div className={`text-sm px-3 py-2 rounded-lg whitespace-pre-line ${saveMsg.startsWith('✓') ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}`}>
          {saveMsg}
        </div>
      )}

      {/* Exchange Selection */}
      <Section title="Exchange">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Exchange">
            <select
              value={settings.exchange_id}
              onChange={e => setSettings({ ...settings, exchange_id: e.target.value })}
              className={inputClass}
            >
              {exchanges.map(ex => (
                <option key={ex.id} value={ex.id}>{ex.name}</option>
              ))}
            </select>
          </Field>
          <Field label="Market Type">
            <select
              value={settings.market_type}
              onChange={e => setSettings({ ...settings, market_type: e.target.value as 'futures' | 'spot' })}
              className={inputClass}
            >
              {selectedExchange?.futures && <option value="futures">Futures (Perpetual)</option>}
              {selectedExchange?.spot && <option value="spot">Spot</option>}
            </select>
          </Field>
        </div>

        <div className="flex items-center gap-3 mt-3">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={settings.testnet}
              onChange={e => setSettings({ ...settings, testnet: e.target.checked })}
              className="w-4 h-4 accent-green-500"
            />
            <span className="text-sm text-gray-300">Testnet / Paper Trading</span>
          </label>
          {!settings.testnet && (
            <span className="text-xs text-red-400 bg-red-900/30 px-2 py-0.5 rounded">
              ⚠ LIVE TRADING — Real money at risk
            </span>
          )}
          {settings.testnet && (
            <span className="text-xs text-green-400 bg-green-900/30 px-2 py-0.5 rounded">
              ✓ Safe — Paper trading mode
            </span>
          )}
        </div>
      </Section>

      {/* API Credentials */}
      <Section title="API Credentials">
        <p className="text-xs text-gray-500 mb-3">
          Keys are encrypted before storage. Leave as '***' to keep existing values.
        </p>
        <div className="space-y-3">
          <Field label="API Key">
            <input
              type="password"
              value={settings.api_key}
              onChange={e => setSettings({ ...settings, api_key: e.target.value })}
              placeholder="Enter API key (or leave *** to keep existing)"
              className={inputClass}
            />
          </Field>
          <Field label="API Secret">
            <input
              type="password"
              value={settings.api_secret}
              onChange={e => setSettings({ ...settings, api_secret: e.target.value })}
              placeholder="Enter API secret (or leave *** to keep existing)"
              className={inputClass}
            />
          </Field>
          {selectedExchange?.needs_passphrase && (
            <Field label="Passphrase (required for this exchange)">
              <input
                type="password"
                value={settings.passphrase}
                onChange={e => setSettings({ ...settings, passphrase: e.target.value })}
                placeholder="Enter passphrase"
                className={inputClass}
              />
            </Field>
          )}
        </div>
      </Section>

      {/* Account & Position Sizing */}
      <Section title="Account & Position Sizing">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Account Balance (USD)">
            <input type="number" value={settings.account_balance_usd}
              onChange={e => setSettings({ ...settings, account_balance_usd: +e.target.value })}
              className={inputClass} min={0} />
          </Field>
          <Field label="Sizing Mode">
            <select value={settings.sizing_mode}
              onChange={e => setSettings({ ...settings, sizing_mode: e.target.value as any })}
              className={inputClass}>
              {SIZING_MODES.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
          </Field>
          {settings.sizing_mode === 'fixed_usd' && (
            <Field label="USD per Trade ($)">
              <input type="number" value={settings.fixed_usd_per_trade}
                onChange={e => setSettings({ ...settings, fixed_usd_per_trade: +e.target.value })}
                className={inputClass} min={1} />
            </Field>
          )}
          {settings.sizing_mode === 'risk_pct' && (
            <Field label="Risk % per Trade (e.g. 0.02 = 2%)">
              <input type="number" value={settings.risk_pct_per_trade}
                onChange={e => setSettings({ ...settings, risk_pct_per_trade: +e.target.value })}
                className={inputClass} min={0.001} max={0.1} step={0.001} />
            </Field>
          )}
          <Field label="Default Leverage">
            <input type="number" value={settings.default_leverage}
              onChange={e => setSettings({ ...settings, default_leverage: +e.target.value })}
              className={inputClass} min={1} max={125} />
          </Field>
          <Field label="Fee Rate (e.g. 0.001 = 0.1%)">
            <input type="number" value={settings.fee_rate}
              onChange={e => setSettings({ ...settings, fee_rate: +e.target.value })}
              className={inputClass} min={0} step={0.0001} />
          </Field>
        </div>
      </Section>

      {/* Assets */}
      <Section title="Assets to Trade">
        <div className="space-y-2 mb-3">
          {settings.assets.map(asset => (
            <div key={asset.symbol} className="flex items-center gap-3 bg-gray-800 rounded-lg px-3 py-2">
              <input type="checkbox" checked={asset.enabled}
                onChange={e => updateAsset(asset.symbol, { enabled: e.target.checked })}
                className="w-4 h-4 accent-green-500" />
              <span className="text-white font-mono text-sm w-28">{asset.symbol}</span>
              <span className="text-xs text-gray-500">Leverage:</span>
              <input type="number"
                value={asset.leverage ?? settings.default_leverage}
                onChange={e => updateAsset(asset.symbol, { leverage: +e.target.value })}
                className="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-0.5 text-sm text-white"
                min={1} max={125} />
              <span className="text-xs text-gray-500">×</span>
              <button onClick={() => removeAsset(asset.symbol)}
                className="ml-auto text-gray-500 hover:text-red-400 text-xs">✕</button>
            </div>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            type="text"
            value={newAsset}
            onChange={e => setNewAsset(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && addAsset()}
            placeholder="Add symbol (e.g. SOL/USDT)"
            className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white placeholder-gray-500"
          />
          <button onClick={addAsset}
            className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-sm text-gray-200 rounded-lg">
            + Add
          </button>
        </div>
      </Section>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Shared UI helpers
// ---------------------------------------------------------------------------

const inputClass = "w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-gray-500"

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3">
      <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wide">{title}</h2>
      {children}
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs text-gray-500 mb-1">{label}</label>
      {children}
    </div>
  )
}
