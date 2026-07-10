import React, { useState, useEffect, useRef } from 'react';

function App() {
  const [logs, setLogs] = useState([]);
  const [budget, setBudget] = useState(100.0);
  const [coherence, setCoherence] = useState(0.0);
  const [activeArms, setActiveArms] = useState(0);
  const [status, setStatus] = useState('IDLE');
  const [prompt, setPrompt] = useState('Determine the optimal routing path for a payload where Path A has 10ms latency but a 5% drop rate, and Path B has 50ms latency but a 0% drop rate. Prioritize speed but guarantee delivery.');
  const [isFlashing, setIsFlashing] = useState(false);
  const [isArbitrating, setIsArbitrating] = useState(false);
  const [finalDecision, setFinalDecision] = useState(null);
  
  const ws = useRef(null);
  const logsEndRef = useRef(null);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const connectWebSocket = () => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.port === '5173' ? 'localhost:8000' : window.location.host;
    ws.current = new WebSocket(`${protocol}//${host}/ws/octopus`);
    
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
          
          if (data.type === 'SEAL') {
            setIsFlashing(true);
            setTimeout(() => setIsFlashing(false), 2000);
          }
          
          if (data.type === 'ARBITRATION') {
            setIsArbitrating(true);
            setTimeout(() => setIsArbitrating(false), 3000);
          }
          
          if (data.type === 'FINAL_OUTPUT') {
            setFinalDecision(data.decision);
            setStatus('COMPLETED');
          } else {
            setStatus('PROCESSING');
          }
        }
      } catch (err) {
        console.error("Failed to parse websocket message", err);
      }
    };
    
    ws.current.onclose = () => {
      setStatus('DISCONNECTED');
      setLogs(prev => [...prev, { type: 'SYSTEM', message: 'Disconnected from Mantle Gateway.' }]);
    };
    
    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  };

  useEffect(() => {
    connectWebSocket();
    return () => {
      if (ws.current) ws.current.close();
    };
  }, []);

  const handleExecute = () => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      setLogs([]);
      setFinalDecision(null);
      setBudget(100.0);
      setCoherence(0.0);
      setActiveArms(0);
      ws.current.send(JSON.stringify({ prompt }));
    } else {
      setLogs(prev => [...prev, { type: 'ERROR', message: 'WebSocket not connected. Is the gateway running?' }]);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 p-8 flex flex-col font-mono selection:bg-cyan-500/30">
      <header className="mb-8 flex justify-between items-end border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
            Consensus Protocol
          </h1>
          <p className="text-slate-500 text-sm mt-1">Blastema Protocol Telemetry Gateway</p>
        </div>
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
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-grow">
        
        {/* Left Column: Controls & Metrics */}
        <div className="space-y-6">
          {/* Controls */}
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

          {/* Metrics */}
          <div className={`glass-panel p-6 transition-all duration-300 ${isFlashing ? 'seal-alert' : ''} ${isArbitrating ? 'arbitration-alert' : ''}`}>
            <h2 className="text-lg font-semibold mb-6 flex justify-between items-center">
              <span>Telemetry</span>
              <div className="flex space-x-2">
                {isFlashing && (
                  <span className="text-xs font-bold bg-red-600 text-white px-2 py-1 rounded animate-pulse">SEAL ACTIVE</span>
                )}
                {isArbitrating && (
                  <span className="text-xs font-bold bg-amber-500 text-slate-900 px-2 py-1 rounded animate-pulse flex items-center shadow-[0_0_15px_rgba(245,158,11,0.6)]">
                    <svg className="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M10 2a1 1 0 011 1v1.323l3.954 1.582 1.599-.8a1 1 0 01.894 1.79l-1.233.616 1.738 5.42a1 1 0 01-.285 1.05A3.989 3.989 0 0115 15a3.989 3.989 0 01-2.667-1.019 1 1 0 01-.285-1.05l1.715-5.349L11 6.477V16h2a1 1 0 110 2H7a1 1 0 110-2h2V6.477L6.237 7.582l1.715 5.349a1 1 0 01-.285 1.05A3.989 3.989 0 015 15a3.989 3.989 0 01-2.667-1.019 1 1 0 01-.285-1.05l1.738-5.42-1.233-.617a1 1 0 01.894-1.788l1.599.799L9 4.323V3a1 1 0 011-1z" clipRule="evenodd"></path></svg>
                    ARBITRATION
                  </span>
                )}
              </div>
            </h2>
            
            {/* Budget Bar */}
            <div className="mb-6">
              <div className="flex justify-between text-sm mb-1">
                <span className="text-slate-400">Metabolic Budget</span>
                <span className="font-mono font-bold text-cyan-400">{budget.toFixed(1)}</span>
              </div>
              <div className="h-3 w-full bg-slate-900 rounded-full overflow-hidden border border-slate-800 relative">
                <div 
                  className="h-full bg-gradient-to-r from-emerald-500 to-cyan-500 transition-all duration-1000 ease-out"
                  style={{ width: `${Math.max(0, Math.min(100, budget))}%` }}
                ></div>
              </div>
            </div>

            {/* Coherence */}
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-slate-400">Resonant Coherence</span>
                <span className={`font-mono font-bold transition-colors ${coherence >= 0.85 ? 'text-emerald-400' : 'text-fuchsia-400'}`}>
                  {coherence.toFixed(2)}
                </span>
              </div>
              <div className="h-3 w-full bg-slate-900 rounded-full overflow-hidden border border-slate-800">
                <div 
                  className={`h-full transition-all duration-500 ${
                    coherence >= 0.85 ? 'bg-gradient-to-r from-green-500 to-emerald-400' : 'bg-gradient-to-r from-purple-500 to-fuchsia-500'
                  }`}
                  style={{ width: `${Math.max(0, Math.min(100, coherence * 100))}%` }}
                ></div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Terminal & Output */}
        <div className="lg:col-span-2 flex flex-col space-y-6">
          
          {/* Output Modal (only shows when complete) */}
          {finalDecision && (
            <div className="glass-panel p-6 border-emerald-500/30 bg-emerald-950/20 shadow-[0_0_30px_rgba(16,185,129,0.1)] animate-fade-in">
              <h2 className="text-emerald-400 text-sm font-bold tracking-wider mb-2 flex items-center">
                <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path></svg>
                CRYSTALLIZED DECISION (MOLT COMPLETE)
              </h2>
              <p className="text-slate-200 text-lg leading-relaxed pl-6 border-l-2 border-emerald-500/50">
                {finalDecision}
              </p>
            </div>
          )}

          {/* Live Terminal */}
          <div className="glass-panel flex-grow flex flex-col overflow-hidden h-[500px]">
            <div className="bg-slate-900/80 px-4 py-2 border-b border-slate-700/50 flex space-x-2 items-center">
              <div className="w-3 h-3 rounded-full bg-red-500/80"></div>
              <div className="w-3 h-3 rounded-full bg-yellow-500/80"></div>
              <div className="w-3 h-3 rounded-full bg-green-500/80"></div>
              <span className="ml-2 text-xs text-slate-500 font-mono flex-grow text-center pr-8">Mantle_Event_Stream.log</span>
            </div>
            
            <div className="p-4 overflow-y-auto font-mono text-sm space-y-2 flex-grow bg-slate-950/50">
              {logs.length === 0 ? (
                <div className="text-slate-600 italic">Waiting for swarm execution...</div>
              ) : (
                logs.map((log, i) => (
                  <div key={i} className="animate-slide-up flex items-start">
                    <span className="text-slate-600 mr-3 text-xs mt-1 shrink-0 w-20">
                      {new Date(log.timestamp || Date.now()).toLocaleTimeString()}
                    </span>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold shrink-0 mr-3 mt-0.5 w-24 text-center ${
                      log.type === 'SEAL' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
                      log.type === 'WARNING' ? 'bg-yellow-500/20 text-yellow-400' :
                      log.type === 'ERROR' ? 'bg-red-500/30 text-red-300 font-bold border border-red-500/50' :
                      log.type === 'CONSENSUS' ? 'bg-emerald-500/20 text-emerald-400' :
                      log.type === 'ARBITRATION' ? 'bg-amber-500 text-slate-900 font-extrabold shadow-[0_0_10px_rgba(245,158,11,0.5)]' :
                      log.type === 'BLASTEMA' ? 'bg-blue-500/20 text-blue-400' :
                      log.type === 'FINAL_OUTPUT' ? 'bg-emerald-600/30 text-emerald-300' :
                      'bg-slate-700/50 text-slate-300'
                    }`}>
                      {log.type === 'ARBITRATION' ? '⚖️ ' + log.type : log.type}
                    </span>
                    <span className={`break-words flex-grow ${
                      log.type === 'SEAL' ? 'text-red-300 font-bold' :
                      log.type === 'ERROR' ? 'text-red-400 font-bold' :
                      log.type === 'CONSENSUS' ? 'text-emerald-300' :
                      log.type === 'ARBITRATION' ? 'text-amber-400 font-bold tracking-wide' :
                      log.type === 'FINAL_OUTPUT' ? 'text-emerald-200 font-bold' :
                      'text-slate-300'
                    }`}>
                      {log.message}
                    </span>
                  </div>
                ))
              )}
              <div ref={logsEndRef} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
