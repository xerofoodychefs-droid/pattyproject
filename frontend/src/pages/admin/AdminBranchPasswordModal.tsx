import React, { useState, useEffect } from 'react';
import { X, Eye, EyeOff, Key, CheckCircle2, UserCheck } from 'lucide-react';
import { api } from '../../api/client';

interface Props {
  branchId: string;
  branchName: string;
  initialAdmin?: {
    name: string;
    email: string;
  } | null;
  onClose: () => void;
  onSuccess: () => void;
}

export const AdminBranchPasswordModal: React.FC<Props> = ({
  branchId,
  branchName,
  initialAdmin,
  onClose,
  onSuccess,
}) => {
  const isEditing = Boolean(initialAdmin && initialAdmin.email);
  const [name, setName] = useState(initialAdmin?.name || `${branchName} Admin`);
  const [email, setEmail] = useState(initialAdmin?.email || '');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    const orig = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = orig;
    };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const cleanEmail = email.trim().toLowerCase();
    if (!cleanEmail || !cleanEmail.includes('@')) {
      setError('Please enter a valid login email address.');
      return;
    }

    if (!name.trim()) {
      setError('Please enter an admin name.');
      return;
    }

    // If new admin or password is provided, validate length and match
    if (!isEditing || newPassword.trim()) {
      if (!isEditing && !newPassword) {
        setError('Password is required for new Branch Admin.');
        return;
      }
      if (newPassword.length < 6) {
        setError('Password must be at least 6 characters long.');
        return;
      }
      if (newPassword !== confirmPassword) {
        setError('Passwords do not match.');
        return;
      }
    }

    setLoading(true);
    try {
      await api.post(`/branches/${branchId}/admin`, {
        name: name.trim(),
        email: cleanEmail,
        password: newPassword.trim() || undefined,
      });

      setSuccess(true);
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 700);
    } catch (err: any) {
      console.error(err);
      setError(err?.detail || err?.message || 'Failed to save Branch Admin credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="admin-modal-overlay">
      <div className="admin-modal-container bg-[#0D0D0D] border border-[#242424] rounded-xl max-w-md shadow-2xl p-4 sm:p-6 relative text-[#F5F5F5] space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-[#1C1C1C] shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-[#241209] border border-[#6B2A0D] flex items-center justify-center text-[#FF5A00] shrink-0">
              {isEditing ? <Key className="w-4.5 h-4.5" /> : <UserCheck className="w-4.5 h-4.5" />}
            </div>
            <div>
              <h2 className="text-base font-semibold text-[#F5F5F5]">
                {isEditing ? 'Edit Branch Admin Credentials' : 'Create Branch Admin'}
              </h2>
              <p className="text-xs text-[#A1A1AA]">Update login credentials for {branchName}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close modal"
            className="p-1 text-[#A1A1AA] hover:text-[#F5F5F5] rounded-lg transition-colors cursor-pointer shrink-0"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {error && (
          <div className="p-3 bg-[#EF4444]/10 border border-[#EF4444]/20 text-[#EF4444] rounded-lg text-xs font-medium shrink-0">
            {error}
          </div>
        )}

        {success && (
          <div className="p-3 bg-[#22C55E]/10 border border-[#22C55E]/20 text-[#22C55E] rounded-lg text-xs font-medium flex items-center gap-2 shrink-0">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>Branch Admin credentials updated successfully!</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex-1 min-h-0 flex flex-col">
          <div className="flex-1 overflow-y-auto pr-1 space-y-3.5">
          <div>
            <label className="block text-[11px] font-semibold text-[#A1A1AA] uppercase mb-1">
              Admin Full Name *
            </label>
            <input
              type="text"
              placeholder="e.g. Camden Branch Manager"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full h-10 bg-[#151515] border border-[#242424] focus:border-[#FF5A00] rounded-lg px-3 text-xs text-[#F5F5F5] placeholder-[#71717A] focus:outline-none transition-colors"
              required
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-[#A1A1AA] uppercase mb-1">
              Login Email Address *
            </label>
            <input
              type="email"
              placeholder="e.g. camden@pattyproject.co.uk"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full h-10 bg-[#151515] border border-[#242424] focus:border-[#FF5A00] rounded-lg px-3 text-xs text-[#F5F5F5] placeholder-[#71717A] focus:outline-none transition-colors"
              required
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-[#A1A1AA] uppercase mb-1">
              {isEditing ? 'New Password (Leave blank to keep current)' : 'Password *'}
            </label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                placeholder={isEditing ? '••••••••' : 'Min 6 characters'}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full h-10 bg-[#151515] border border-[#242424] focus:border-[#FF5A00] rounded-lg pl-3 pr-10 text-xs text-[#F5F5F5] placeholder-[#71717A] focus:outline-none transition-colors"
                required={!isEditing}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-2.5 text-[#71717A] hover:text-[#F5F5F5] cursor-pointer"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {(!isEditing || newPassword.length > 0) && (
            <div>
              <label className="block text-[11px] font-semibold text-[#A1A1AA] uppercase mb-1">
                Confirm Password *
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  placeholder="Confirm password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full h-10 bg-[#151515] border border-[#242424] focus:border-[#FF5A00] rounded-lg pl-3 pr-10 text-xs text-[#F5F5F5] placeholder-[#71717A] focus:outline-none transition-colors"
                  required
                />
              </div>
            </div>
          )}
          </div>

          <div className="pt-4 mt-4 flex flex-wrap items-center justify-end gap-2.5 border-t border-[#1C1C1C] shrink-0">
            <button
              type="button"
              onClick={onClose}
              className="h-9 px-4 bg-[#151515] border border-[#242424] hover:border-[#333333] text-[#A1A1AA] hover:text-[#F5F5F5] rounded-lg text-xs font-semibold transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || success}
              className="h-9 px-4 bg-[#FF5A00] hover:bg-[#E84F00] text-white rounded-lg text-xs font-semibold transition-colors shadow-sm disabled:opacity-50 cursor-pointer"
            >
              {loading ? 'Saving...' : isEditing ? 'Update Credentials' : 'Create Admin'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
