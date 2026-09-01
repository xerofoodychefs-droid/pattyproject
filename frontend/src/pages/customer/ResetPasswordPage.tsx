import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { Lock, Eye, EyeOff, CheckCircle2, AlertTriangle, AlertCircle, Loader2, ArrowRight, KeyRound, ShieldCheck } from 'lucide-react';
import { api } from '../../api/client';

export const ResetPasswordPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const token = searchParams.get('token')?.trim() || '';

  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const isMinLength = newPassword.length >= 8;
  const isMatch = newPassword.length > 0 && newPassword === confirmPassword;
  const isFormValid = isMinLength && isMatch;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!token) {
      setError('Missing or invalid reset token. Please request a new password reset link.');
      return;
    }

    if (!isMinLength) {
      setError('Password must be at least 8 characters long.');
      return;
    }

    if (!isMatch) {
      setError('Passwords do not match. Please ensure both passwords are identical.');
      return;
    }

    setLoading(true);

    try {
      await api.post('/auth/reset-password', {
        token: token,
        new_password: newPassword.trim(),
      });

      // Clear token from browser URL upon completion
      window.history.replaceState({}, document.title, window.location.pathname);

      setSuccess(true);
    } catch (err: any) {
      setError(err?.message || 'Invalid or expired password reset link. Please request a fresh reset link.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#070707] text-white flex flex-col justify-between relative overflow-x-hidden">
      {/* Desktop Right Side Hero Burger Background */}
      <div className="hidden lg:block absolute inset-y-0 right-0 w-[55%] xl:w-[58%] pointer-events-none overflow-hidden z-0">
        <div className="relative w-full h-full">
          <img
            src="/herobackground.webp"
            alt="Patty Project Hero"
            loading="lazy"
            decoding="async"
            onError={(e) => { (e.currentTarget as HTMLImageElement).src = '/herobackground.png'; }}
            className="w-full h-full object-cover object-center select-none"
          />
          <div className="absolute inset-0 bg-gradient-to-r from-[#070707] via-[#070707]/70 to-transparent" />
          <div className="absolute inset-0 bg-gradient-to-t from-[#070707] via-transparent to-[#070707]/80" />
        </div>
      </div>

      {/* Main Content Area */}
      <div className="relative z-10 flex-1 flex items-center justify-center px-4 sm:px-6 py-12 lg:py-20 lg:justify-start lg:pl-16 xl:pl-28">
        <div className="w-full max-w-md space-y-6">
          {/* Header Brand */}
          <div className="space-y-2">
            <Link to="/" className="inline-block">
              <span className="text-xs font-black text-[#FF5A00] uppercase tracking-widest">
                PATTY PROJECT UK
              </span>
            </Link>
            <h1 className="text-2xl sm:text-3xl font-black text-white uppercase tracking-tight">
              Set New Password
            </h1>
            <p className="text-xs sm:text-sm text-[#A1A1AA]">
              Choose a strong, secure password to protect your Patty Project account.
            </p>
          </div>

          {/* Missing Token Warning */}
          {!token && !success && (
            <div className="bg-[#1C130D] border border-[#7C2D12] rounded-2xl p-5 text-center space-y-3">
              <div className="w-12 h-12 rounded-full bg-[#EA580C]/10 text-[#EA580C] border border-[#EA580C]/20 flex items-center justify-center mx-auto">
                <AlertTriangle className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <h3 className="text-sm font-bold text-white">Invalid Reset Link</h3>
                <p className="text-xs text-[#A1A1AA]">
                  No reset token was found in the link. Please request a new password reset link from the login page.
                </p>
              </div>
              <Link
                to="/login"
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#FF5A00] hover:bg-[#E84F00] text-white text-xs font-bold uppercase tracking-wider rounded-xl transition-all shadow-lg shadow-[#FF5A00]/25"
              >
                <span>Back to Login</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          )}

          {/* Success Card */}
          {success && (
            <div className="bg-gradient-to-b from-[#10B981]/15 to-[#121212] border border-[#10B981]/30 rounded-3xl p-6 sm:p-8 text-center space-y-4 shadow-2xl animate-in zoom-in-90 duration-300">
              <div className="w-16 h-16 bg-[#10B981]/20 text-[#10B981] border border-[#10B981]/40 rounded-full flex items-center justify-center mx-auto shadow-xl shadow-[#10B981]/20">
                <CheckCircle2 className="w-9 h-9 stroke-[2.5]" />
              </div>
              <div className="space-y-2">
                <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight">
                  Password Updated!
                </h2>
                <p className="text-xs sm:text-sm text-[#A1A1AA] leading-relaxed">
                  Your password has been successfully reset. All previous active sessions have been signed out for security.
                </p>
              </div>
              <div className="pt-2">
                <Link
                  to="/login"
                  className="w-full h-12 bg-[#FF5A00] hover:bg-[#E84F00] text-white font-extrabold text-xs uppercase tracking-wider rounded-xl transition-all shadow-lg shadow-[#FF5A00]/25 flex items-center justify-center gap-2 cursor-pointer"
                >
                  <span>Sign In with New Password</span>
                  <ArrowRight className="w-4 h-4" />
                </Link>
              </div>
            </div>
          )}

          {/* Reset Form */}
          {token && !success && (
            <div className="bg-[#121212] border border-[#242424] p-6 sm:p-8 rounded-3xl space-y-5 shadow-2xl">
              {error && (
                <div className="p-3.5 bg-[#2B1111] border border-[#6B2121] rounded-xl flex items-start gap-2.5 text-xs text-[#F87171] animate-in fade-in duration-200">
                  <AlertCircle className="w-4 h-4 text-[#EF4444] flex-shrink-0 mt-0.5" />
                  <span>{error}</span>
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                {/* New Password */}
                <div className="space-y-1.5 text-left">
                  <label className="text-xs font-bold text-[#A1A1AA] uppercase tracking-wider">
                    New Password
                  </label>
                  <div className="relative">
                    <Lock className="w-4 h-4 text-[#71717A] absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                    <input
                      type={showNewPassword ? 'text' : 'password'}
                      required
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      placeholder="Minimum 8 characters"
                      className="w-full h-12 bg-[#181818] border border-[#2B2B2B] focus:border-[#FF5A00] rounded-xl pl-10 pr-10 text-sm text-white placeholder-[#52525B] focus:outline-none transition-colors"
                    />
                    <button
                      type="button"
                      onClick={() => setShowNewPassword(!showNewPassword)}
                      className="absolute right-3.5 top-1/2 -translate-y-1/2 text-[#71717A] hover:text-white transition-colors cursor-pointer"
                    >
                      {showNewPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                {/* Confirm Password */}
                <div className="space-y-1.5 text-left">
                  <label className="text-xs font-bold text-[#A1A1AA] uppercase tracking-wider">
                    Confirm New Password
                  </label>
                  <div className="relative">
                    <Lock className="w-4 h-4 text-[#71717A] absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                    <input
                      type={showConfirmPassword ? 'text' : 'password'}
                      required
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="Re-enter your new password"
                      className="w-full h-12 bg-[#181818] border border-[#2B2B2B] focus:border-[#FF5A00] rounded-xl pl-10 pr-10 text-sm text-white placeholder-[#52525B] focus:outline-none transition-colors"
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                      className="absolute right-3.5 top-1/2 -translate-y-1/2 text-[#71717A] hover:text-white transition-colors cursor-pointer"
                    >
                      {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                {/* Password Requirements Checklist */}
                <div className="p-3 bg-[#181818] border border-[#242424] rounded-xl space-y-1.5 text-[11px] text-left">
                  <div className={`flex items-center gap-2 ${isMinLength ? 'text-[#10B981]' : 'text-[#71717A]'}`}>
                    <ShieldCheck className="w-3.5 h-3.5 flex-shrink-0" />
                    <span>At least 8 characters long</span>
                  </div>
                  <div className={`flex items-center gap-2 ${isMatch ? 'text-[#10B981]' : 'text-[#71717A]'}`}>
                    <ShieldCheck className="w-3.5 h-3.5 flex-shrink-0" />
                    <span>Passwords match</span>
                  </div>
                </div>

                {/* Submit Button */}
                <button
                  type="submit"
                  disabled={loading || !isFormValid}
                  className="w-full h-12 bg-[#FF5A00] hover:bg-[#E84F00] text-white font-black text-xs uppercase tracking-wider rounded-xl transition-all shadow-lg shadow-[#FF5A00]/25 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <>
                      <span>RESET PASSWORD</span>
                      <ArrowRight className="w-4 h-4" />
                    </>
                  )}
                </button>
              </form>

              <div className="pt-2 text-center">
                <Link
                  to="/login"
                  className="text-xs text-[#71717A] hover:text-white transition-colors inline-block"
                >
                  Remember your password? <span className="text-[#FF5A00] font-bold">Sign In</span>
                </Link>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
