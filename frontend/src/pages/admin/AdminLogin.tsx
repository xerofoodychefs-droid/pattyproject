import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { User, Lock, Eye, EyeOff, ShieldCheck } from 'lucide-react';
import { api } from '../../api/client';
import { useAuthStore } from '../../store/authStore';

export const AdminLogin: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const { setAuth } = useAuthStore();
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    const cleanEmail = email.trim().toLowerCase();
    if (!cleanEmail) {
      setError('Please enter your email address.');
      return;
    }
    if (!password) {
      setError('Please enter your password.');
      return;
    }

    setLoading(true);

    try {
      // Clear any stale session credentials before attempting fresh login
      localStorage.removeItem('patty_token');
      localStorage.removeItem('patty_refresh_token');
      localStorage.removeItem('patty_user');

      const res: any = await api.post('/auth/login', { email: cleanEmail, password });
      
      if (!res || !res.access_token || !res.user) {
        setError('Invalid response received from authentication server.');
        return;
      }

      if (res.user.role !== 'SUPER_ADMIN' && res.user.role !== 'BRANCH_ADMIN') {
        setError('Access denied. Administrator privileges required to access this portal.');
        return;
      }

      setAuth(res.access_token, res.user, res.refresh_token);
      navigate('/admin/dashboard', { replace: true });
    } catch (err: any) {
      const errMsg = err?.detail || err?.message || 'Incorrect email or password.';
      setError(errMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0B0B0B] text-white flex items-center justify-center p-4 relative overflow-hidden">
      {/* Glow ember background effect */}
      <div className="absolute top-1/4 right-10 w-96 h-96 bg-[#FF5500]/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-10 left-10 w-80 h-80 bg-[#FF5500]/5 rounded-full blur-3xl pointer-events-none" />

      <div className="w-full max-w-md bg-[#121212] border border-[#262626] rounded-2xl p-8 shadow-2xl relative z-10">
        {/* Brand Logo Header */}
        <div className="flex flex-col items-center text-center mb-8">
          <img src="/logo.png" alt="Patty Project" className="w-24 h-24 object-contain mb-4" />
          <h1 className="text-2xl font-bold text-white tracking-wide">Admin Login</h1>
          <p className="text-[#9CA3AF] text-sm mt-1">Welcome back! Please login to your account.</p>
        </div>

        {error && (
          <div className="mb-6 p-3 bg-[#2A1212] border border-[#EF4444]/40 text-[#EF4444] rounded-xl text-sm text-center">
            {error}
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-5">
          {/* Email / Username Input */}
          <div>
            <label className="block text-xs font-semibold text-[#9CA3AF] uppercase mb-2">Email or Username</label>
            <div className="relative">
              <User className="w-5 h-5 absolute left-3.5 top-3.5 text-[#6B7280]" />
              <input
                type="text"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Enter email or username"
                className="w-full bg-[#1A1A1A] border border-[#262626] focus:border-[#FF5500] rounded-xl py-3 pl-11 pr-4 text-white text-sm focus:outline-none transition-colors"
                required
              />
            </div>
          </div>

          {/* Password Input */}
          <div>
            <label className="block text-xs font-semibold text-[#9CA3AF] uppercase mb-2">Password</label>
            <div className="relative">
              <Lock className="w-5 h-5 absolute left-3.5 top-3.5 text-[#6B7280]" />
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password"
                className="w-full bg-[#1A1A1A] border border-[#262626] focus:border-[#FF5500] rounded-xl py-3 pl-11 pr-11 text-white text-sm focus:outline-none transition-colors"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3.5 top-3.5 text-[#6B7280] hover:text-white transition-colors"
              >
                {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
              </button>
            </div>
          </div>

          {/* Options Row */}
          <div className="flex items-center justify-between text-sm">
            <label className="flex items-center gap-2 text-[#9CA3AF] cursor-pointer">
              <input
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                className="w-4 h-4 rounded bg-[#1A1A1A] border-[#262626] accent-[#FF5500]"
              />
              <span>Remember Me</span>
            </label>
            <a href="#" className="text-[#FF5500] hover:underline font-medium">Forgot Password?</a>
          </div>

          {/* Primary Submit Button */}
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-[#FF5500] hover:bg-[#E04B00] text-white font-bold py-3.5 rounded-xl transition-all shadow-lg shadow-[#FF5500]/25 disabled:opacity-50"
          >
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>

        {/* Divider */}
        <div className="relative my-6 text-center">
          <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-[#262626]"></div></div>
          <span className="relative bg-[#121212] px-4 text-xs text-[#6B7280]">or continue with</span>
        </div>

        {/* Social Sign in */}
        <button
          type="button"
          className="w-full bg-[#1A1A1A] hover:bg-[#222222] border border-[#262626] text-white font-medium py-3 rounded-xl flex items-center justify-center gap-3 transition-colors text-sm"
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24">
            <path fill="#EA4335" d="M12 5c1.6 0 3 .6 4.1 1.7l3.1-3.1C17.3 1.8 14.8 1 12 1 7.5 1 3.7 3.6 1.9 7.3l3.7 2.9C6.5 7.4 9 5 12 5z" />
            <path fill="#4285F4" d="M23.5 12.3c0-.8-.1-1.6-.2-2.3H12v4.5h6.5c-.3 1.5-1.1 2.8-2.4 3.7l3.7 2.9c2.2-2 3.7-5 3.7-8.8z" />
            <path fill="#FBBC05" d="M5.6 14.8c-.2-.7-.4-1.5-.4-2.3s.2-1.6.4-2.3L1.9 7.3C.7 9.7 0 12 0 14.5s.7 4.8 1.9 7.2l3.7-2.9z" />
            <path fill="#34A853" d="M12 23c3.2 0 6-1.1 8-3l-3.7-2.9c-1.1.7-2.5 1.2-4.3 1.2-3 0-5.5-2.4-6.4-5.2L1.9 16C3.7 19.7 7.5 22.3 12 23z" />
          </svg>
          <span>Sign in with Google</span>
        </button>

        {/* Security Badge */}
        <div className="mt-8 flex items-center justify-center gap-2 text-xs text-[#6B7280]">
          <ShieldCheck className="w-4 h-4 text-[#10B981]" />
          <span>Secure admin access only</span>
        </div>
      </div>
    </div>
  );
};
