import React, { useState, useEffect } from 'react';
import { getPendingApprovals, respondToApproval } from '../utils/api';

const ApprovalQueue = ({ onUpdate }) => {
  const [approvals, setApprovals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);
  const [responding, setResponding] = useState(null);

  const fetchApprovals = async () => {
    try {
      const res = await getPendingApprovals();
      setApprovals(res.data);
    } catch (error) {
      console.error('Error fetching approvals:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchApprovals();
  }, []);

  const handleApprove = async (approval) => {
    setResponding(approval.id);
    try {
      await respondToApproval(approval.id, {
        approved: true,
        admin_response: 'Approved',
        responded_by: 'user'
      });
      
      // Remove from list
      setApprovals(approvals.filter(a => a.id !== approval.id));
      
      if (onUpdate) onUpdate();
      
      // Show success notification
      alert('✅ Tool approved and execution started!');
    } catch (error) {
      console.error('Error approving:', error);
      alert('❌ Error approving tool');
    } finally {
      setResponding(null);
    }
  };

  const handleReject = async (approval) => {
    setResponding(approval.id);
    try {
      await respondToApproval(approval.id, {
        approved: false,
        admin_response: 'Rejected',
        responded_by: 'user'
      });
      
      // Remove from list
      setApprovals(approvals.filter(a => a.id !== approval.id));
      
      if (onUpdate) onUpdate();
      
      alert('🚫 Tool rejected');
    } catch (error) {
      console.error('Error rejecting:', error);
      alert('❌ Error rejecting tool');
    } finally {
      setResponding(null);
    }
  };

  if (loading) {
    return (
      <div className="bg-gray-800 rounded-lg p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-4 bg-gray-700 rounded w-1/4"></div>
          <div className="h-20 bg-gray-700 rounded"></div>
          <div className="h-20 bg-gray-700 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gray-800 rounded-lg p-6 shadow-lg">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-white flex items-center">
          <span className="mr-2">⏳</span>
          Approval Queue
          {approvals.length > 0 && (
            <span className="ml-3 px-3 py-1 bg-yellow-500 text-black text-sm rounded-full">
              {approvals.length}
            </span>
          )}
        </h2>
        <button
          onClick={fetchApprovals}
          className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded transition"
        >
          🔄 Refresh
        </button>
      </div>

      {approvals.length === 0 ? (
        <div className="text-center py-12">
          <div className="text-6xl mb-4">✅</div>
          <p className="text-gray-400 text-lg">No pending approvals</p>
          <p className="text-gray-500 text-sm mt-2">
            Tool requests will appear here when detected
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {approvals.map((approval) => (
            <div
              key={approval.id}
              className="bg-gray-700 rounded-lg p-4 border-l-4 border-yellow-500"
            >
              {/* Header */}
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h3 className="text-lg font-semibold text-white flex items-center">
                    {approval.tool_name}
                    {approval.auto_detected && (
                      <span className="ml-2 px-2 py-1 bg-purple-600 text-xs rounded">
                        Auto-detected
                      </span>
                    )}
                  </h3>
                  <p className="text-sm text-gray-400 mt-1">
                    Requested by: {approval.requested_by} • {new Date(approval.requested_at).toLocaleString()}
                  </p>
                </div>
                <span className="px-3 py-1 bg-yellow-600 text-white text-xs rounded-full">
                  Pending
                </span>
              </div>

              {/* Note */}
              {approval.requester_note && (
                <div className="mb-3 p-3 bg-gray-600 rounded text-sm text-gray-300">
                  <strong>Note:</strong> {approval.requester_note}
                </div>
              )}

              {/* Code Preview */}
              <div className="mb-4">
                <button
                  onClick={() => setExpandedId(expandedId === approval.id ? null : approval.id)}
                  className="text-blue-400 hover:text-blue-300 text-sm mb-2"
                >
                  {expandedId === approval.id ? '▼' : '▶'} View Code
                </button>
                
                {expandedId === approval.id && (
                  <pre className="bg-gray-900 text-green-400 p-4 rounded text-sm overflow-x-auto max-h-64 overflow-y-auto">
                    <code>{approval.tool_code}</code>
                  </pre>
                )}
              </div>

              {/* Actions */}
              <div className="flex gap-3">
                <button
                  onClick={() => handleApprove(approval)}
                  disabled={responding === approval.id}
                  className="flex-1 px-4 py-2 bg-green-600 hover:bg-green-500 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded font-medium transition"
                >
                  {responding === approval.id ? '⏳ Approving...' : '✅ Approve & Execute'}
                </button>
                <button
                  onClick={() => handleReject(approval)}
                  disabled={responding === approval.id}
                  className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-500 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded font-medium transition"
                >
                  {responding === approval.id ? '⏳ Rejecting...' : '🚫 Reject'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default ApprovalQueue;
