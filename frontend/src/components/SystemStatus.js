import React, { useState, useEffect } from 'react';
import { getStatus, getMonitorStatus } from '../utils/api';

const SystemStatus = ({ wsConnected }) => {
  const [status, setStatus] = useState(null);
  const [monitorStatus, setMonitorStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchStatus = async () => {
    try {
      const [statusRes, monitorRes] = await Promise.all([
        getStatus(),
        getMonitorStatus()
      ]);
      setStatus(statusRes.data);
      setMonitorStatus(monitorRes.data);
    } catch (error) {
      console.error('Error fetching status:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000); // Refresh every 5s
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="bg-gray-800 rounded-lg p-6 animate-pulse">
        <div className="h-4 bg-gray-700 rounded w-1/4 mb-4"></div>
        <div className="space-y-2">
          <div className="h-3 bg-gray-700 rounded"></div>
          <div className="h-3 bg-gray-700 rounded w-5/6"></div>
        </div>
      </div>
    );
  }

  const getStatusColor = (connected) => connected ? 'bg-green-500' : 'bg-red-500';
  const getStatusText = (connected) => connected ? 'Connected' : 'Disconnected';

  return (
    <div className="bg-gray-800 rounded-lg p-6 shadow-lg">
      <h2 className="text-xl font-bold text-white mb-4 flex items-center">
        <span className="mr-2">📊</span>
        System Status
      </h2>

      <div className="space-y-4">
        {/* KoboldCPP Status */}
        <div className="flex items-center justify-between p-3 bg-gray-700 rounded">
          <div className="flex items-center">
            <div className={`w-3 h-3 rounded-full ${getStatusColor(status?.koboldcpp?.connected)} mr-3`}></div>
            <span className="text-gray-300 font-medium">KoboldCPP</span>
          </div>
          <span className="text-sm text-gray-400">
            {getStatusText(status?.koboldcpp?.connected)}
          </span>
        </div>

        {/* Monitor Status */}
        <div className="flex items-center justify-between p-3 bg-gray-700 rounded">
          <div className="flex items-center">
            <div className={`w-3 h-3 rounded-full ${getStatusColor(monitorStatus?.enabled)} mr-3`}></div>
            <span className="text-gray-300 font-medium">Monitor</span>
          </div>
          <span className="text-sm text-gray-400">
            {monitorStatus?.enabled ? 'Active' : 'Inactive'}
          </span>
        </div>

        {/* WebSocket Status */}
        <div className="flex items-center justify-between p-3 bg-gray-700 rounded">
          <div className="flex items-center">
            <div className={`w-3 h-3 rounded-full ${getStatusColor(wsConnected)} mr-3`}></div>
            <span className="text-gray-300 font-medium">WebSocket</span>
          </div>
          <span className="text-sm text-gray-400">
            {getStatusText(wsConnected)}
          </span>
        </div>

        {/* Stats */}
        {status && (
          <div className="mt-4 pt-4 border-t border-gray-700">
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="p-2 bg-gray-700 rounded">
                <div className="text-gray-400">Pending Approvals</div>
                <div className="text-xl font-bold text-yellow-400">
                  {status.approvals?.pending || 0}
                </div>
              </div>
              <div className="p-2 bg-gray-700 rounded">
                <div className="text-gray-400">Total Approvals</div>
                <div className="text-xl font-bold text-blue-400">
                  {status.approvals?.total || 0}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Processed Count */}
        {monitorStatus && (
          <div className="text-xs text-gray-500 mt-2">
            Patterns processed: {monitorStatus.processed_count || 0}
          </div>
        )}
      </div>
    </div>
  );
};

export default SystemStatus;
