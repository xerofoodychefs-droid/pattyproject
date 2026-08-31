import React, { useState, useEffect } from 'react';
import { Lock, CheckCircle2, Key, Trash2, Edit, Check, AlertCircle, Loader2, UserCheck, ShieldAlert } from 'lucide-react';
import { api } from '../../api/client';
import { Branch, BranchAdmin } from '../../types';
import { AdminBranchPasswordModal } from './AdminBranchPasswordModal';

interface BranchWithAdmin extends Branch {
  admin?: BranchAdmin | null;
}

export const AdminProfileSettings: React.FC = () => {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  // Live branches and their admins
  const [branches, setBranches] = useState<BranchWithAdmin[]>([]);
  const [branchesLoading, setBranchesLoading] = useState(true);
  const [selectedBranch, setSelectedBranch] = useState<{ id: string; name: string; admin?: BranchAdmin | null } | null>(null);
  const [deletingAdminId, setDeletingAdminId] = useState<string | null>(null);

  useEffect(() => {
    fetchBranchesWithAdmins();
  }, []);

  const fetchBranchesWithAdmins = async () => {
    setBranchesLoading(true);
    try {
      const branchList = await api.get<Branch[]>('/branches');
      if (Array.isArray(branchList)) {
        // Fetch admin info for each branch
        const withAdmins = await Promise.all(
          branchList.map(async (b) => {
            try {
              const admin = await api.get<BranchAdmin | null>(`/branches/${b.id}/admin`);
              return { ...b, admin };
            } catch {
              return { ...b, admin: null };
            }
          })
        );
        setBranches(withAdmins);
      }
    } catch (err: any) {
      console.error('Failed to load branches:', err);
    } finally {
      setBranchesLoading(false);
    }
  };

  const handleUpdatePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg('');
    setSuccessMsg('');

    if (newPassword.length < 8) {
      setErrorMsg('New password must be at least 8 characters long');
      return;
    }

    if (newPassword !== confirmPassword) {
      setErrorMsg('New passwords do not match');
      return;
    }

    setLoading(true);
    try {
      await api.post('/auth/change-password', {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setSuccessMsg('Password updated successfully!');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to update password. Please check your current password.');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteAdmin = async (branchId: string, branchName: string) => {
    if (!window.confirm(`Are you sure you want to remove the Branch Admin for ${branchName}? The user account will be deactivated.`)) {
      return;
    }

    setDeletingAdminId(branchId);
    try {
      await api.delete(`/branches/${branchId}/admin`);
      setSuccessMsg(`Branch Admin removed for ${branchName}.`);
      await fetchBranchesWithAdmins();
    } catch (err: any) {
      console.error(err);
      setErrorMsg(err?.detail || err?.message || 'Failed to remove Branch Admin.');
    } finally {
      setDeletingAdminId(null);
    }
  };

  return (
    <div className="p-4 sm:p-6 lg:p-8 w-full max-w-[1680px] mx-auto space-y-6 text-[#F5F5F5]">
      {/* Page Header */}
      <div>
        <h1 className="text-3xl font-bold text-[#F5F5F5] tracking-tight">Profile Settings</h1>
        <p className="text-sm text-[#A1A1AA] font-normal mt-1">Manage your account settings and Branch Admin login credentials.</p>
      </div>

      {errorMsg && (
        <div className="p-3.5 bg-[#EF4444]/10 border border-[#EF4444]/30 text-[#EF4444] rounded-lg text-xs font-semibold flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {successMsg && (
        <div className="p-3.5 bg-[#22C55E]/10 border border-[#22C55E]/30 text-[#22C55E] rounded-lg text-xs font-semibold flex items-center gap-2">
          <Check className="w-4 h-4 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Top Card: Change Admin Password */}
      <div className="bg-[#0D0D0D] border border-[#242424] p-5 sm:p-6 rounded-xl shadow-sm space-y-6">
        <div className="flex items-center gap-3 pb-4 border-b border-[#1C1C1C]">
          <div className="w-9 h-9 rounded-lg bg-[#241209] border border-[#6B2A0D] flex items-center justify-center text-[#FF5A00] shrink-0">
            <Lock className="w-4.5 h-4.5" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-[#F5F5F5]">Change Super Admin Password</h2>
            <p className="text-xs text-[#A1A1AA]">Update your main administrator password.</p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          <form onSubmit={handleUpdatePassword} className="lg:col-span-8 space-y-4">
            <div>
              <label className="block text-[11px] font-semibold text-[#A1A1AA] uppercase mb-1">Current Password *</label>
              <input
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                placeholder="Enter current password"
                className="w-full h-10 bg-[#151515] border border-[#242424] focus:border-[#FF5A00] rounded-lg px-3.5 text-xs text-[#F5F5F5] placeholder-[#71717A] focus:outline-none transition-colors"
                required
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-[#A1A1AA] uppercase mb-1">New Password *</label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Enter new password"
                className="w-full h-10 bg-[#151515] border border-[#242424] focus:border-[#FF5A00] rounded-lg px-3.5 text-xs text-[#F5F5F5] placeholder-[#71717A] focus:outline-none transition-colors"
                required
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-[#A1A1AA] uppercase mb-1">Confirm New Password *</label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Confirm new password"
                className="w-full h-10 bg-[#151515] border border-[#242424] focus:border-[#FF5A00] rounded-lg px-3.5 text-xs text-[#F5F5F5] placeholder-[#71717A] focus:outline-none transition-colors"
                required
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="h-10 px-5 bg-[#FF5A00] hover:bg-[#E84F00] text-white text-xs font-semibold rounded-lg shadow-sm transition-colors cursor-pointer flex items-center gap-2 disabled:opacity-50"
            >
              {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              <span>{loading ? 'Updating Password...' : 'Update Password'}</span>
            </button>
          </form>

          {/* Password Requirements Checklist Right */}
          <div className="lg:col-span-4 bg-[#151515] border border-[#242424] p-4.5 rounded-lg space-y-3">
            <h3 className="text-xs font-semibold text-[#F5F5F5] uppercase tracking-wider">Password Requirements</h3>
            <div className="space-y-2.5 text-xs text-[#A1A1AA]">
              <div className="flex items-center gap-2 text-[#22C55E]">
                <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                <span>At least 8 characters long</span>
              </div>
              <div className="flex items-center gap-2 text-[#22C55E]">
                <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                <span>Include uppercase and lowercase</span>
              </div>
              <div className="flex items-center gap-2 text-[#22C55E]">
                <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                <span>Include at least one number</span>
              </div>
              <div className="flex items-center gap-2 text-[#22C55E]">
                <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                <span>Include at least one special char</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Card: Branch Admin Credentials */}
      <div className="bg-[#0D0D0D] border border-[#242424] p-5 sm:p-6 rounded-xl shadow-sm space-y-5">
        <div className="flex items-center justify-between pb-4 border-b border-[#1C1C1C]">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-[#241209] border border-[#6B2A0D] flex items-center justify-center text-[#FF5A00] shrink-0">
              <Key className="w-4.5 h-4.5" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-[#F5F5F5]">Branch Admin Login Credentials</h2>
              <p className="text-xs text-[#A1A1AA]">Configure login email and credentials for each branch portal.</p>
            </div>
          </div>
          <button
            onClick={fetchBranchesWithAdmins}
            className="text-xs text-[#A1A1AA] hover:text-[#FF5A00] transition-colors cursor-pointer"
          >
            Refresh
          </button>
        </div>

        <div className="bg-[#0D0D0D] border border-[#242424] rounded-xl overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead className="bg-[#171717] text-[#A1A1AA] uppercase text-[11px] font-semibold border-b border-[#1C1C1C]">
                <tr>
                  <th className="px-5 py-3.5">Branch</th>
                  <th className="px-5 py-3.5">Admin Full Name</th>
                  <th className="px-5 py-3.5">Login Email</th>
                  <th className="px-5 py-3.5">Status</th>
                  <th className="px-5 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1C1C1C] bg-[#0D0D0D]">
                {branchesLoading ? (
                  <tr>
                    <td colSpan={5} className="px-5 py-8 text-center text-[#71717A]">
                      <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2 text-[#FF5A00]" />
                      <span>Loading branch credentials...</span>
                    </td>
                  </tr>
                ) : branches.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-5 py-8 text-center text-[#71717A]">
                      No branches found. Create a branch from the Dashboard to configure credentials.
                    </td>
                  </tr>
                ) : (
                  branches.map((b) => (
                    <tr key={b.id} className="hover:bg-[#121212] transition-colors h-14">
                      <td className="px-5 py-3 font-semibold text-[#F5F5F5]">
                        <div>{b.name}</div>
                        <div className="text-[10px] text-[#71717A] font-mono">{b.code}</div>
                      </td>
                      <td className="px-5 py-3 text-[#A1A1AA]">
                        {b.admin?.name || <span className="text-[#52525B] italic">Not set</span>}
                      </td>
                      <td className="px-5 py-3 font-mono text-[#F5F5F5]">
                        {b.admin?.email ? (
                          <span className="text-[#FF5A00] font-medium">{b.admin.email}</span>
                        ) : (
                          <span className="text-[#EF4444]/80 italic">Not configured</span>
                        )}
                      </td>
                      <td className="px-5 py-3">
                        {b.admin ? (
                          b.admin.is_active ? (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-[#22C55E]/10 text-[#22C55E] border border-[#22C55E]/20">
                              Active
                            </span>
                          ) : (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-[#EF4444]/10 text-[#EF4444] border border-[#EF4444]/20">
                              Deactivated
                            </span>
                          )
                        ) : (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-[#EAB308]/10 text-[#EAB308] border border-[#EAB308]/20">
                            Unconfigured
                          </span>
                        )}
                      </td>
                      <td className="px-5 py-3 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => setSelectedBranch({ id: b.id, name: b.name, admin: b.admin })}
                            className="h-8 px-3 bg-[#151515] border border-[#242424] text-[#FF5A00] hover:bg-[#FF5A00] hover:text-white rounded-lg text-xs font-semibold transition-colors cursor-pointer"
                          >
                            {b.admin ? 'Edit Credentials' : 'Create Admin'}
                          </button>
                          {b.admin && (
                            <button
                              onClick={() => handleDeleteAdmin(b.id, b.name)}
                              disabled={deletingAdminId === b.id}
                              className="w-8 h-8 rounded-lg bg-[#151515] border border-[#242424] text-[#71717A] hover:text-[#EF4444] hover:border-[#EF4444]/40 hover:bg-[#EF4444]/10 inline-flex items-center justify-center transition-colors cursor-pointer disabled:opacity-50"
                              title="Remove Branch Admin"
                              aria-label="Remove branch admin"
                            >
                              {deletingAdminId === b.id ? (
                                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              ) : (
                                <Trash2 className="w-3.5 h-3.5" />
                              )}
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        <p className="text-xs text-[#71717A]">
          ⓘ Branch Admin accounts use their Login Email and Password to sign in at the Admin Portal.
        </p>
      </div>

      {selectedBranch && (
        <AdminBranchPasswordModal
          branchId={selectedBranch.id}
          branchName={selectedBranch.name}
          initialAdmin={selectedBranch.admin ? { name: selectedBranch.admin.name, email: selectedBranch.admin.email } : null}
          onClose={() => setSelectedBranch(null)}
          onSuccess={() => {
            setSuccessMsg(`Credentials updated for ${selectedBranch.name}`);
            setSelectedBranch(null);
            fetchBranchesWithAdmins();
          }}
        />
      )}
    </div>
  );
};
