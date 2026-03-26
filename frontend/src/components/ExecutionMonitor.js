import React, { useState, useEffect } from 'react';
import { getExecutionStatistics, cancelExecution } from '../utils/api';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const ExecutionMonitor = ({ wsMessage }) => {
  const [activeExecutions, setActiveExecutions] = useState([]);
  const [statistics, setStatistics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [terminating, setTerminating] = useState(null);
  const [shutdownConfig, setShutdownConfig] = useState({});

  const fetchActiveExecutions = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/executions/active/list`);
      setActiveExecutions(response.data.active_executions || []);
    } catch (error) {
      console.error('Error fetching active executions:', error);
    }
  };

  const fetchStatistics = async () => {
    try {
      const stats = await getExecutionStatistics();
      setStatistics(stats.data);
    } catch (error) {
      console.error('Error fetching statistics:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchActiveExecutions();
    fetchStatistics();
    
    const interval = setInterval(() => {
      fetchActiveExecutions();
      fetchStatistics();
    }, 3000); // Refresh every 3 seconds

    return () => clearInterval(interval);
  }, []);

  // Update on WebSocket messages
  useEffect(() => {
    if (wsMessage) {
      if (wsMessage.type === 'execution_status' || 
          wsMessage.type === 'tool_update' ||
          wsMessage.type === 'emergency_shutdown') {
        fetchActiveExecutions();
        fetchStatistics();
      }
    }
  }, [wsMessage]);

  const handleTerminate = async (executionId, method) => {
    setTerminating(executionId);
    
    try {
      const config = shutdownConfig[executionId] || {};
      await cancelExecution(executionId, { method, ...config });
      
      // Refresh list
      await fetchActiveExecutions();
      await fetchStatistics();
      
      alert(`✅ Execution ${method} terminated successfully`);
    } catch (error) {
      console.error('Error terminating:', error);
      alert(`❌ Error: ${error.response?.data?.detail || error.message}`);
    } finally {
      setTerminating(null);
    }
  };

  const handleEmergencyShutdown = async () => {
    const confirmed = window.confirm(
      '⚠️ EMERGENCY SHUTDOWN: This will terminate ALL running executions. Continue?'
    );
    
    if (!confirmed) return;

    try {
      await axios.post(`${BACKEND_URL}/api/executions/terminate/all`, {
        method: 'immediate'
      });
      
      alert('✅ All executions terminated');
      await fetchActiveExecutions();
      await fetchStatistics();
    } catch (error) {
      alert(`❌ Error: ${error.message}`);
    }
  };

  const updateShutdownConfig = (executionId, field, value) => {
    setShutdownConfig(prev => ({
      ...prev,
      [executionId]: {
        ...prev[executionId],
        [field]: value
      }
    }));
  };

  const formatDuration = (seconds) => {
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}m ${secs}s`;
  };

  if (loading) {
    return (
      <div className="bg-gray-800 rounded-lg p-6 animate-pulse">
        <div className="h-4 bg-gray-700 rounded w-1/4 mb-4"></div>
        <div className="h-20 bg-gray-700 rounded"></div>
      </div>
    );
  }

  return (
    <div className="bg-gray-800 rounded-lg p-6 shadow-lg">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-white flex items-center">
          <span className="mr-2">⚙️</span>
          Active Executions
          {activeExecutions.length > 0 && (
            <span className="ml-3 px-3 py-1 bg-green-500 text-black text-sm rounded-full animate-pulse">
              {activeExecutions.length} Running
            </span>
          )}
        </h2>
        
        {activeExecutions.length > 0 && (
          <button
            onClick={handleEmergencyShutdown}
            className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded font-medium transition"
          >
            🚨 Emergency Stop All
          </button>
        )}
      </div>

      {/* Statistics */}
      {statistics && (
        <div className="grid grid-cols-4 gap-4 mb-6">
          <div className="bg-gray-700 rounded p-4">
            <div className="text-gray-400 text-sm">Total Executions</div>
            <div className="text-2xl font-bold text-white">{statistics.total_executions}</div>
          </div>
          <div className="bg-gray-700 rounded p-4">
            <div className="text-gray-400 text-sm">Completed</div>
            <div className="text-2xl font-bold text-green-400">{statistics.completed}</div>
          </div>
          <div className="bg-gray-700 rounded p-4">
            <div className="text-gray-400 text-sm">Failed</div>
            <div className="text-2xl font-bold text-red-400">{statistics.failed}</div>
          </div>
          <div className="bg-gray-700 rounded p-4">
            <div className="text-gray-400 text-sm">Languages</div>
            <div className="text-sm text-gray-300">
              {Object.keys(statistics.by_language || {}).join(', ') || 'None'}
            </div>
          </div>
        </div>
      )}

      {/* Active Executions List */}
      {activeExecutions.length === 0 ? (
        <div className="text-center py-12">
          <div className="text-6xl mb-4">✅</div>
          <p className="text-gray-400 text-lg">No active executions</p>
          <p className="text-gray-500 text-sm mt-2">
            Running processes will appear here
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {activeExecutions.map((exec) => {
            const config = shutdownConfig[exec.execution_id] || {};
            
            return (
              <div
                key={exec.execution_id}
                className="bg-gray-700 rounded-lg p-4 border-l-4 border-green-500"
              >
                {/* Execution Info */}
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="text-lg font-semibold text-white flex items-center">
                      {exec.language.toUpperCase()} Execution
                      <span className="ml-2 px-2 py-1 bg-green-600 text-xs rounded animate-pulse">
                        RUNNING
                      </span>
                    </h3>
                    <p className="text-sm text-gray-400 mt-1">
                      ID: {exec.execution_id.substring(0, 8)}... • PID: {exec.pid}
                    </p>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-bold text-white">
                      {formatDuration(exec.elapsed_time)}
                    </div>
                    <div className="text-xs text-gray-400">elapsed</div>
                  </div>
                </div>

                {/* Resource Limits */}
                <div className="mb-4 p-3 bg-gray-600 rounded text-sm">
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <span className="text-gray-400">Memory Limit:</span>
                      <span className="text-white ml-2">{exec.resource_limits.max_memory_mb}MB</span>
                    </div>
                    <div>
                      <span className="text-gray-400">Timeout:</span>
                      <span className="text-white ml-2">{exec.resource_limits.max_execution_time}s</span>
                    </div>
                    <div>
                      <span className="text-gray-400">Network:</span>
                      <span className="text-white ml-2">
                        {exec.resource_limits.network_enabled ? '✅ Enabled' : '🚫 Disabled'}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Shutdown Configuration */}
                <div className="mb-4 space-y-2">
                  <div className="text-sm font-semibold text-gray-300">Shutdown Options:</div>
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      type="text"
                      placeholder="Custom command (optional)"
                      value={config.custom_command || ''}
                      onChange={(e) => updateShutdownConfig(
                        exec.execution_id,
                        'custom_command',
                        e.target.value
                      )}
                      className="px-3 py-2 bg-gray-600 text-white rounded text-sm"
                    />
                    <input
                      type="number"
                      placeholder="Grace period (s)"
                      value={config.grace_period || 5}
                      onChange={(e) => updateShutdownConfig(
                        exec.execution_id,
                        'grace_period',
                        parseInt(e.target.value)
                      )}
                      className="px-3 py-2 bg-gray-600 text-white rounded text-sm"
                    />
                  </div>
                </div>

                {/* Termination Buttons */}
                <div className="grid grid-cols-3 gap-2">
                  <button
                    onClick={() => handleTerminate(exec.execution_id, 'graceful')}
                    disabled={terminating === exec.execution_id}
                    className="px-4 py-2 bg-yellow-600 hover:bg-yellow-500 disabled:bg-gray-600 text-white rounded font-medium transition"
                  >
                    {terminating === exec.execution_id ? '⏳' : '⏸️'} Graceful
                  </button>
                  
                  <button
                    onClick={() => handleTerminate(exec.execution_id, 'immediate')}
                    disabled={terminating === exec.execution_id}
                    className="px-4 py-2 bg-red-600 hover:bg-red-500 disabled:bg-gray-600 text-white rounded font-medium transition"
                  >
                    {terminating === exec.execution_id ? '⏳' : '🛑'} Force Kill
                  </button>
                  
                  {config.custom_command && (
                    <button
                      onClick={() => handleTerminate(exec.execution_id, 'custom')}
                      disabled={terminating === exec.execution_id}
                      className="px-4 py-2 bg-purple-600 hover:bg-purple-500 disabled:bg-gray-600 text-white rounded font-medium transition"
                    >
                      {terminating === exec.execution_id ? '⏳' : '⚙️'} Custom
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default ExecutionMonitor;
