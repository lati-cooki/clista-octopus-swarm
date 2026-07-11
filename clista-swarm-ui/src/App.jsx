import React, { useState, useEffect, useRef } from 'react';

// Truncate a long identifier for compact display, keeping it fully visible via title/tooltip.
const truncateId = (id, len = 14) => {
  if (!id) return '—';
  const str = String(id);
  return str.length > len ? `${str.slice(0, len)}…` : str;
};

// Render only the date portion of an ISO timestamp (or any parseable date string).
const formatDatePart = (dateStr) => {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return String(dateStr).split('T')[0] || String(dateStr);
  return d.toLocaleDateString();
};

function App() {
  const [activeTab, setActiveTab] = useState('swarm'); // 'swarm' or 'audit'

  // --- SWARM STATE ---
  const [logs, setLogs] = useState([]);
  const [budget, setBudget] = useState(100.0);
  const [coherence, setCoherence] = useState(0.0);
  const [activeArms, setActiveArms] = useState(0);
  const [status, setStatus] = useState('IDLE');
  const [prompt, setPrompt] = useState('');
  const [isFlashing, setIsFlashing] = useState(false);
  const [isArbitrating, setIsArbitrating] = useState(false);
  const [isRecalling, setIsRecalling] = useState(false);
  const [finalDecision, setFinalDecision] = useState(null);
  const [finalPrecedent, setFinalPrecedent] = useState(null);
  const ws = useRef(null);
  const logsEndRef = useRef(null);

  // --- AUDIT STATE ---
  const [auditLogs, setAuditLogs] = useState([]);
  const [loadingAudit, setLoadingAudit] = useState(false);
  const [selectedAudit, setSelectedAudit] = useState(null); // the record to show in the modal

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const connectWebSocket = () => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.port === '5173' ? 'localhost:8000' : window.location.host;
    const token = "SUPER_SECRET_TOKEN"; // In production, fetch this from a secure store or env
    ws.current = new WebSocket(`${protocol}//${host}/ws/octopus?token=${token}`);
    
    ws.current.onopen = () => {
      setStatus('CONNECTED');
      setLogs([{ type: 'SYSTEM', message: 'Connected to Mantle Gateway.' }]);
    };
    
    ws.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type) {
          setLogs(prev => [...prev, data]);
          if (data.budget !== undefined) setBudget(data.budget);
          if (data.coherence !== undefined) setCoherence(data.coherence);
          if (data.active_arms !== undefined) setActiveArms(data.active_arms);
          if (data.type === 'SEAL') { setIsFlashing(true); setTimeout(() => setIsFlashing(false), 2000); }
          if (data.type === 'ARBITRATION') { setIsArbitrating(true); setTimeout(() => setIsArbitrating(false), 3000); }
          if (data.type === 'RECALL') { setIsRecalling(true); setTimeout(() => setIsRecalling(false), 2500); }
          if (data.type === 'FINAL_OUTPUT') { setFinalDecision(data.decision); setFinalPrecedent(data.precedent || null); setStatus('COMPLETED'); }
          else { setStatus('PROCESSING'); }
        }
      } catch (err) { console.error("Failed to parse websocket message", err); }
    };
    
    ws.current.onclose = () => {
      setStatus('DISCONNECTED');
      setLogs(prev => [...prev, { type: 'SYSTEM', message: 'Disconnected from Mantle Gateway.' }]);
    };
  };

  useEffect(() => {
    connectWebSocket();
    return () => { if (ws.current) ws.current.close(); };
  }, []);

  const handleExecute = () => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      setLogs([]); setFinalDecision(null); setFinalPrecedent(null); setBudget(100.0); setCoherence(0.0); setActiveArms(0);
      ws.current.send(JSON.stringify({ prompt }));
    } else {
      setLogs(prev => [...prev, { type: 'ERROR', message: 'WebSocket not connected. Is the gateway running?' }]);
    }
  };

  const fetchAuditLogs = async () => {
    setLoadingAudit(true);
    try {
      const protocol = window.location.protocol;
      const host = window.location.port === '5173' ? 'localhost:8000' : window.location.host;
      const token = "SUPER_SECRET_TOKEN";
      const res = await fetch(`${protocol}//${host}/api/audit/logs`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      const json = await res.json();
      if (json.status === 'success') {
        setAuditLogs(json.data);
      }
    } catch (e) {
      console.error("Failed to fetch audit logs", e);
    }
    setLoadingAudit(false);
  };

  useEffect(() => {
    if (activeTab === 'audit') {
      fetchAuditLogs();
    }
  }, [activeTab]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 flex flex-col font-mono selection:bg-cyan-500/30 overflow-hidden relative">
      <header className="px-8 pt-8 pb-4 flex justify-between items-end border-b border-slate-800">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent flex items-center gap-3">
            🐙 Consensus Protocol
          </h1>
          <div className="flex gap-4 mt-4">
            <button 
              onClick={() => setActiveTab('swarm')}
              className={`px-4 py-1.5 rounded-md text-sm font-bold transition-all ${activeTab === 'swarm' ? 'bg-cyan-900/50 text-cyan-400 border border-cyan-500/50 shadow-[0_0_10px_rgba(6,182,212,0.3)]' : 'text-slate-500 hover:text-slate-300'}`}
            >
              Live Swarm
            </button>
            <button 
              onClick={() => setActiveTab('audit')}
              className={`px-4 py-1.5 rounded-md text-sm font-bold transition-all ${activeTab === 'audit' ? 'bg-emerald-900/50 text-emerald-400 border border-emerald-500/50 shadow-[0_0_10px_rgba(16,185,129,0.3)]' : 'text-slate-500 hover:text-slate-300'}`}
            >
              MRM Audit Ledger
            </button>
          </div>
        </div>
        
        {activeTab === 'swarm' && (
          <div className="flex items-center space-x-4">
            <div className="text-right mr-4">
              <span className="text-xs text-slate-500 block mb-1">ACTIVE ARMS</span>
              <div className="flex space-x-1 justify-end">
                {[1, 2, 3].map(i => (
                  <div key={i} className={`w-3 h-3 rounded-full transition-all duration-300 ${
                    i <= activeArms 
                      ? i === 3 ? 'bg-amber-500 shadow-[0_0_10px_rgba(245,158,11,0.8)]' : 'bg-cyan-500 shadow-[0_0_8px_rgba(6,182,212,0.6)]'
                      : 'bg-slate-800'
                  }`}></div>
                ))}
              </div>
            </div>
            <div className="flex flex-col text-right">
              <span className="text-xs text-slate-500 mb-1">GATEWAY STATUS</span>
              <span className={`px-2 py-1 rounded text-[10px] font-bold ${
                status === 'CONNECTED' || status === 'PROCESSING' || status === 'COMPLETED'
                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                  : 'bg-red-500/20 text-red-400 border border-red-500/30'
              }`}>
                {status}
              </span>
            </div>
          </div>
        )}
      </header>

      <main className="p-8 flex-grow flex flex-col overflow-hidden relative">
        {activeTab === 'swarm' ? (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-grow">
            {/* Swarm Left Column */}
            <div className="space-y-6">
              <div className="glass-panel p-6">
                <h2 className="text-lg font-semibold mb-4 text-slate-300">Swarm Injection</h2>
                <textarea
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-sm focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all min-h-[120px] mb-4"
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="Enter task prompt..."
                />
                <button
                  onClick={handleExecute}
                  disabled={status === 'PROCESSING' || status === 'DISCONNECTED'}
                  className="w-full bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-semibold py-2 px-4 rounded-lg transition-all disabled:opacity-50 shadow-[0_0_15px_rgba(8,145,178,0.4)] hover:shadow-[0_0_25px_rgba(8,145,178,0.6)]"
                >
                  {status === 'PROCESSING' ? 'Swarm Executing...' : 'Execute Swarm'}
                </button>
              </div>

              <div className={`glass-panel p-6 transition-all duration-300 ${isFlashing ? 'seal-alert' : ''} ${isArbitrating ? 'arbitration-alert' : ''} ${isRecalling ? 'recall-alert' : ''}`}>
                <h2 className="text-lg font-semibold mb-6 flex justify-between items-center">
                  <span>Telemetry</span>
                  <div className="flex space-x-2">
                    {isFlashing && (
                      <span className="text-xs font-bold bg-red-600 text-white px-2 py-1 rounded animate-pulse">SEAL ACTIVE</span>
                    )}
                    {isArbitrating && (
                      <span className="text-xs font-bold bg-amber-500 text-slate-900 px-2 py-1 rounded animate-pulse shadow-[0_0_15px_rgba(245,158,11,0.6)]">ARBITRATION</span>
                    )}
                    {isRecalling && (
                      <span className="text-xs font-bold bg-sky-400 text-slate-900 px-2 py-1 rounded animate-pulse shadow-[0_0_15px_rgba(56,189,248,0.7)]">CACHE RECALL</span>
                    )}
                  </div>
                </h2>
                <div className="mb-6">
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-slate-400">Metabolic Budget</span>
                    <span className="font-mono font-bold text-cyan-400">{budget.toFixed(1)}</span>
                  </div>
                  <div className="h-3 w-full bg-slate-900 rounded-full overflow-hidden border border-slate-800">
                    <div className="h-full bg-gradient-to-r from-emerald-500 to-cyan-500 transition-all duration-1000" style={{ width: `${Math.max(0, Math.min(100, budget))}%` }}></div>
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-slate-400">Resonant Coherence</span>
                    <span className={`font-mono font-bold ${coherence >= 0.85 ? 'text-emerald-400' : 'text-fuchsia-400'}`}>{coherence.toFixed(2)}</span>
                  </div>
                  <div className="h-3 w-full bg-slate-900 rounded-full overflow-hidden border border-slate-800">
                    <div className={`h-full transition-all duration-500 ${coherence >= 0.85 ? 'bg-gradient-to-r from-green-500 to-emerald-400' : 'bg-gradient-to-r from-purple-500 to-fuchsia-500'}`} style={{ width: `${Math.max(0, Math.min(100, coherence * 100))}%` }}></div>
                  </div>
                </div>
              </div>
            </div>

            {/* Swarm Right Column */}
            <div className="lg:col-span-2 flex flex-col space-y-6">
              {finalDecision && (
                <div className={`glass-panel p-6 animate-fade-in ${finalPrecedent ? 'border-sky-500/30 bg-sky-950/20 shadow-[0_0_30px_rgba(56,189,248,0.12)]' : 'border-emerald-500/30 bg-emerald-950/20 shadow-[0_0_30px_rgba(16,185,129,0.1)]'}`}>
                  <h2 className={`text-sm font-bold tracking-wider mb-2 ${finalPrecedent ? 'text-sky-400' : 'text-emerald-400'}`}>
                    {finalPrecedent ? 'RECALLED DECISION (CACHE HIT)' : 'CRYSTALLIZED DECISION (MOLT COMPLETE)'}
                  </h2>
                  <p className={`text-slate-200 text-lg leading-relaxed pl-6 border-l-2 ${finalPrecedent ? 'border-sky-500/50' : 'border-emerald-500/50'}`}>{finalDecision}</p>
                  {finalPrecedent && (
                    <div className="mt-4 pt-4 border-t border-sky-500/20 flex flex-wrap items-center gap-2">
                      <span className="px-2 py-1 rounded text-[10px] font-bold bg-sky-500/20 text-sky-300 border border-sky-500/40 tracking-wider">
                        PRECEDENT
                      </span>
                      <span className="text-xs text-slate-400 font-mono" title={finalPrecedent.precedent_id}>
                        ID: <span className="text-sky-300">{truncateId(finalPrecedent.precedent_id)}</span>
                      </span>
                      {finalPrecedent.age_days !== undefined && (
                        <span className="text-xs text-slate-400">{finalPrecedent.age_days}d old</span>
                      )}
                      <span className="text-xs text-slate-400">
                        Decided {formatDatePart(finalPrecedent.original_decision_date)}
                      </span>
                      {finalPrecedent.stale && (
                        <span className="px-2 py-1 rounded text-[10px] font-bold bg-red-500/20 text-red-300 border border-red-500/40 animate-pulse">
                          STALE
                        </span>
                      )}
                    </div>
                  )}
                </div>
              )}
              <div className="glass-panel flex-grow flex flex-col overflow-hidden h-[500px]">
                <div className="bg-slate-900/80 px-4 py-2 border-b border-slate-700/50 flex space-x-2 items-center">
                  <div className="w-3 h-3 rounded-full bg-red-500/80"></div>
                  <div className="w-3 h-3 rounded-full bg-yellow-500/80"></div>
                  <div className="w-3 h-3 rounded-full bg-green-500/80"></div>
                  <span className="ml-2 text-xs text-slate-500 text-center flex-grow pr-8">Mantle_Event_Stream.log</span>
                </div>
                <div className="p-4 overflow-y-auto text-sm space-y-2 flex-grow bg-slate-950/50">
                  {logs.length === 0 ? (
                    <div className="text-slate-600 italic">Waiting for swarm execution...</div>
                  ) : (
                    logs.map((log, i) => (
                      <div key={i} className="flex items-start">
                        <span className="text-slate-600 mr-3 text-xs mt-1 w-20 shrink-0">{new Date(log.timestamp || Date.now()).toLocaleTimeString()}</span>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold shrink-0 mr-3 mt-0.5 w-24 text-center ${log.type === 'SEAL' ? 'bg-red-500/20 text-red-400' : log.type === 'WARNING' ? 'bg-yellow-500/20 text-yellow-400' : log.type === 'ERROR' ? 'bg-red-500/30 text-red-300' : log.type === 'CONSENSUS' ? 'bg-emerald-500/20 text-emerald-400' : log.type === 'ARBITRATION' ? 'bg-amber-500 text-slate-900' : log.type === 'RECALL' ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40' : log.type === 'BLASTEMA' ? 'bg-blue-500/20 text-blue-400' : log.type === 'FINAL_OUTPUT' ? 'bg-emerald-600/30 text-emerald-300' : 'bg-slate-700/50 text-slate-300'}`}>{log.type}</span>
                        <span className={`break-words flex-grow ${log.type === 'SEAL' || log.type === 'ERROR' ? 'text-red-300' : log.type === 'CONSENSUS' || log.type === 'FINAL_OUTPUT' ? 'text-emerald-300' : log.type === 'ARBITRATION' ? 'text-amber-400 font-bold' : log.type === 'RECALL' ? 'text-sky-300 font-semibold' : 'text-slate-300'}`}>{log.message}</span>
                      </div>
                    ))
                  )}
                  <div ref={logsEndRef} />
                </div>
              </div>
            </div>
          </div>
        ) : (
          /* Audit Ledger Tab */
          <div className="glass-panel p-6 flex flex-col h-full flex-grow relative overflow-hidden animate-fade-in">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-bold text-emerald-400">MRM Compliance Ledger</h2>
              <button onClick={fetchAuditLogs} className="px-4 py-2 bg-emerald-900/50 hover:bg-emerald-800/50 text-emerald-300 rounded border border-emerald-500/30 transition-all text-sm shadow-[0_0_10px_rgba(16,185,129,0.2)]">
                {loadingAudit ? 'Refreshing...' : 'Refresh Ledger'}
              </button>
            </div>
            <div className="overflow-auto flex-grow rounded-lg border border-slate-800 bg-slate-950/50">
              <table className="w-full text-left text-sm whitespace-nowrap">
                <thead className="bg-slate-900 text-slate-400 uppercase text-xs sticky top-0 z-10 shadow-md">
                  <tr>
                    <th className="px-6 py-4">Timestamp</th>
                    <th className="px-6 py-4">Prompt</th>
                    <th className="px-6 py-4">Decision</th>
                    <th className="px-6 py-4">Coherence</th>
                    <th className="px-6 py-4">Inspect</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50">
                  {auditLogs.length === 0 ? (
                    <tr><td colSpan="5" className="text-center py-8 text-slate-500">{loadingAudit ? 'Fetching Immutable Records...' : 'No audit logs found in Firestore.'}</td></tr>
                  ) : (
                    auditLogs.map((log) => (
                      <tr key={log.record_id} className="hover:bg-slate-800/30 transition-colors">
                        <td className="px-6 py-4 text-slate-500">{new Date(log.timestamp).toLocaleString()}</td>
                        <td className="px-6 py-4 text-slate-300 truncate max-w-[200px]" title={log.prompt}>{log.prompt}</td>
                        <td className="px-6 py-4 text-emerald-400 truncate max-w-[200px]" title={log.final_decision}>{log.final_decision}</td>
                        <td className="px-6 py-4">
                          <span className={`px-2 py-1 rounded text-xs ${(log.metadata?.coherence || 0) >= 0.85 ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'}`}>
                            {(log.metadata?.coherence || 0).toFixed(2)}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <button 
                            onClick={() => setSelectedAudit(log)}
                            className="text-cyan-400 hover:text-cyan-300 bg-cyan-900/30 hover:bg-cyan-800/50 px-3 py-1 rounded border border-cyan-500/30 transition-all"
                          >
                            View Scratchpads
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>

      {/* Slide-out Modal for Audit Inspection */}
      {selectedAudit && (
        <div className="fixed inset-0 z-50 flex items-center justify-end bg-black/60 backdrop-blur-sm animate-fade-in">
          <div className="w-full max-w-4xl h-full bg-slate-900 border-l border-emerald-500/30 shadow-[-10px_0_30px_rgba(16,185,129,0.1)] flex flex-col transform translate-x-0 transition-transform duration-300">
            <div className="p-6 border-b border-slate-800 flex justify-between items-center bg-slate-950">
              <div>
                <h3 className="text-xl font-bold text-emerald-400">Execution History</h3>
                <p className="text-xs text-slate-500 mt-1">ID: {selectedAudit.record_id}</p>
              </div>
              <button onClick={() => setSelectedAudit(null)} className="p-2 text-slate-400 hover:text-white rounded-full hover:bg-slate-800 transition-colors">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path></svg>
              </button>
            </div>
            
            <div className="flex-grow overflow-y-auto p-6 space-y-8 bg-slate-900">
              <div className="space-y-2">
                <h4 className="text-xs uppercase text-slate-500 font-bold tracking-wider">Prompt</h4>
                <div className="bg-slate-950 p-4 rounded border border-slate-800 text-slate-300 text-sm whitespace-pre-wrap">{selectedAudit.prompt}</div>
              </div>
              
              <div className="space-y-4">
                <h4 className="text-xs uppercase text-emerald-500 font-bold tracking-wider">Unmolted Scratchpads (Raw Reasoning)</h4>
                {(selectedAudit.arms_execution_history || []).map((arm, idx) => (
                  <div key={idx} className="bg-slate-950 border border-slate-800 rounded overflow-hidden">
                    <div className="bg-slate-800/50 p-3 border-b border-slate-800 flex justify-between items-center">
                      <span className="font-bold text-cyan-400 text-sm">{arm.arm_id}</span>
                      <div className="flex gap-2">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${arm.status === 'ACTIVE' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-red-500/20 text-red-400 border border-red-500/30'}`}>{arm.status}</span>
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-700/50 text-slate-300 border border-slate-600">Weight: {arm.confidence_weight?.toFixed(2)}</span>
                      </div>
                    </div>
                    <div className="p-4 text-sm text-slate-300 whitespace-pre-wrap font-mono leading-relaxed bg-[#0a0a0f]">
                      {arm.scratchpad || <span className="text-slate-600 italic">No scratchpad data recorded.</span>}
                    </div>
                  </div>
                ))}
              </div>
              
              <div className="space-y-2 pb-8">
                <h4 className="text-xs uppercase text-emerald-400 font-bold tracking-wider">Final Decision</h4>
                <div className="bg-emerald-950/20 p-4 rounded border border-emerald-500/30 text-emerald-300 text-sm whitespace-pre-wrap leading-relaxed">{selectedAudit.final_decision}</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
