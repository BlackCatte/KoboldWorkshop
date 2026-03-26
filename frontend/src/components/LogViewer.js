import React, { useState, useEffect, useRef } from 'react';
import { getRecentLogs } from '../utils/api';

const LogViewer = ({ wsMessage }) => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all'); // all, info, warning, error
  const [autoScroll, setAutoScroll] = useState(true);
  const logsEndRef = useRef(null);

  const fetchLogs = async () => {
    try {
      const res = await getRecentLogs({ limit: 100 });
      setLogs(res.data);
    } catch (error) {
      console.error('Error fetching logs:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  // Handle WebSocket log messages
  useEffect(() => {
    if (wsMessage && wsMessage.type === 'log') {
      const newLog = {
        id: Date.now().toString(),
        level: wsMessage.level,
        message: wsMessage.message,
        source: wsMessage.source,
        timestamp: wsMessage.timestamp || new Date().toISOString()
      };
      setLogs(prev => [newLog, ...prev].slice(0, 100)); // Keep last 100
    }
  }, [wsMessage]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  const getLevelColor = (level) => {
    const colors = {
      debug: 'text-gray-400',
      info: 'text-blue-400',
      warning: 'text-yellow-400',
      error: 'text-red-400',
      critical: 'text-red-600'
    };
    return colors[level] || 'text-gray-300';
  };

  const getLevelBadge = (level) => {
    const badges = {
      debug: 'bg-gray-600',
      info: 'bg-blue-600',
      warning: 'bg-yellow-600',
      error: 'bg-red-600',
      critical: 'bg-red-700'
    };
    return badges[level] || 'bg-gray-600';
  };

  const filteredLogs = filter === 'all'
    ? logs
    : logs.filter(log => log.level === filter);

  if (loading) {
    return (
      <div className="bg-gray-800 rounded-lg p-6">
        <div className="animate-pulse space-y-2">
          <div className="h-4 bg-gray-700 rounded w-1/4"></div>
          <div className="h-32 bg-gray-700 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gray-800 rounded-lg p-6 shadow-lg">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-2xl font-bold text-white flex items-center">
          <span className="mr-2">📋</span>
          System Logs
          <span className="ml-3 text-sm text-gray-400">({filteredLogs.length})</span>
        </h2>
        
        <div className="flex items-center gap-3">
          {/* Filter */}
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="px-3 py-2 bg-gray-700 text-white rounded"
          >
            <option value="all">All Levels</option>
            <option value="info">Info</option>
            <option value="warning">Warning</option>
            <option value="error">Error</option>
          </select>

          {/* Auto-scroll toggle */}
          <button
            onClick={() => setAutoScroll(!autoScroll)}
            className={`px-3 py-2 rounded ${autoScroll ? 'bg-green-600' : 'bg-gray-700'} text-white`}
          >
            {autoScroll ? '📌 Auto-scroll ON' : '📌 Auto-scroll OFF'}
          </button>

          {/* Refresh */}
          <button
            onClick={fetchLogs}
            className="px-3 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded"
          >
            🔄
          </button>
        </div>
      </div>

      {/* Logs Container */}
      <div className="bg-gray-900 rounded p-4 h-96 overflow-y-auto font-mono text-sm">
        {filteredLogs.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            No logs to display
          </div>
        ) : (
          filteredLogs.map((log) => (
            <div key={log.id} className="mb-2 hover:bg-gray-800 p-2 rounded">
              <div className="flex items-start gap-2">
                <span className={`px-2 py-0.5 rounded text-xs font-bold ${getLevelBadge(log.level)} text-white`}>
                  {log.level.toUpperCase()}
                </span>
                <span className="text-gray-500 text-xs">
                  {new Date(log.timestamp).toLocaleTimeString()}
                </span>
                <span className="text-gray-600 text-xs">
                  [{log.source}]
                </span>
                <span className={`flex-1 ${getLevelColor(log.level)}`}>
                  {log.message}
                </span>
              </div>
            </div>
          ))
        )}
        <div ref={logsEndRef} />
      </div>

      {/* Stats */}
      <div className="mt-4 flex gap-4 text-xs text-gray-400">
        <div>
          <span className="text-blue-400">{logs.filter(l => l.level === 'info').length}</span> Info
        </div>
        <div>
          <span className="text-yellow-400">{logs.filter(l => l.level === 'warning').length}</span> Warnings
        </div>
        <div>
          <span className="text-red-400">{logs.filter(l => l.level === 'error').length}</span> Errors
        </div>
      </div>
    </div>
  );
};

export default LogViewer;
