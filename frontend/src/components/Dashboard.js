import React, { useState } from 'react';
import useWebSocket from '../hooks/useWebSocket';
import SystemStatus from './SystemStatus';
import ApprovalQueue from './ApprovalQueue';
import LogViewer from './LogViewer';

const Dashboard = () => {
  const [notifications, setNotifications] = useState([]);

  const handleWebSocketMessage = (message) => {
    console.log('WebSocket message:', message);

    // Handle different message types
    if (message.type === 'approval_request') {
      setNotifications(prev => [...prev, {
        id: Date.now(),
        type: 'approval',
        message: `New approval request: ${message.data?.tool_name}`,
        timestamp: new Date()
      }]);
      
      // Play sound or show browser notification
      if ('Notification' in window && Notification.permission === 'granted') {
        new Notification('New Approval Request', {
          body: `Tool: ${message.data?.tool_name}`,
          icon: '/favicon.ico'
        });
      }
    }

    if (message.type === 'tool_detected') {
      setNotifications(prev => [...prev, {
        id: Date.now(),
        type: 'detection',
        message: `Tool pattern detected: ${message.data?.patterns_matched?.join(', ')}`,
        timestamp: new Date()
      }]);
    }
  };

  const { isConnected, lastMessage } = useWebSocket(handleWebSocketMessage);

  // Request notification permission on mount
  React.useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }
  }, []);

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold flex items-center">
              <span className="mr-3">🤖</span>
              AI Tool Monitor
            </h1>
            <p className="text-gray-400 text-sm mt-1">
              Monitoring KoboldCPP • Real-time Tool Detection & Approval
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></div>
            <span className="text-sm text-gray-400">
              {isConnected ? 'Live' : 'Disconnected'}
            </span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Notifications Bar */}
        {notifications.length > 0 && (
          <div className="mb-6 space-y-2">
            {notifications.slice(-3).reverse().map((notif) => (
              <div
                key={notif.id}
                className="bg-yellow-600 text-black px-4 py-3 rounded-lg flex items-center justify-between animate-slideIn"
              >
                <span className="font-medium">{notif.message}</span>
                <button
                  onClick={() => setNotifications(prev => prev.filter(n => n.id !== notif.id))}
                  className="text-black hover:text-gray-700"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
          {/* System Status - Sidebar */}
          <div className="lg:col-span-1">
            <SystemStatus wsConnected={isConnected} />
          </div>

          {/* Main Content Area */}
          <div className="lg:col-span-2 space-y-6">
            {/* Approval Queue */}
            <ApprovalQueue onUpdate={() => console.log('Approval updated')} />
          </div>
        </div>

        {/* Logs - Full Width */}
        <div className="mt-6">
          <LogViewer wsMessage={lastMessage} />
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-gray-800 border-t border-gray-700 px-6 py-4 mt-12">
        <div className="max-w-7xl mx-auto text-center text-gray-400 text-sm">
          <p>AI Tool Monitor v1.0 • Built with FastAPI + React + MongoDB</p>
          <p className="mt-1">Monitoring your AI's tool creation in real-time 🚀</p>
        </div>
      </footer>
    </div>
  );
};

export default Dashboard;
