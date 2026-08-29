import React, { useState, useEffect, useCallback } from 'react';
import {
  Search,
  Gift,
  Award,
  Zap,
  TrendingUp,
  Settings,
  Users,
  RotateCcw,
  Plus,
  Edit2,
  Trash2,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Clock,
  ShieldCheck,
  Power,
  RefreshCw,
  ArrowRight,
  Sliders,
  DollarSign
} from 'lucide-react';
import { api } from '../../api/client';
import {
  LoyaltyMemberSummary,
  LoyaltyAnalytics,
  LoyaltyProgramConfig,
  LoyaltyCampaign,
  LoyaltyMilestone,
  LoyaltyTransaction
} from '../../types';

export const AdminLoyalty: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'members' | 'campaigns' | 'milestones' | 'transactions' | 'settings'>('members');
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Core Data States
  const [stats, setStats] = useState<LoyaltyAnalytics | null>(null);
  const [config, setConfig] = useState<LoyaltyProgramConfig | null>(null);
  const [members, setMembers] = useState<LoyaltyMemberSummary[]>([]);
  const [campaigns, setCampaigns] = useState<LoyaltyCampaign[]>([]);
  const [milestones, setMilestones] = useState<LoyaltyMilestone[]>([]);
  const [transactions, setTransactions] = useState<LoyaltyTransaction[]>([]);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [txTypeFilter, setTxTypeFilter] = useState('ALL');

  // Manual Adjustment Modal State
  const [adjustModalOpen, setAdjustModalOpen] = useState(false);
  const [selectedMember, setSelectedMember] = useState<LoyaltyMemberSummary | null>(null);
  const [adjustType, setAdjustType] = useState<'CREDIT' | 'DEBIT'>('CREDIT');
  const [adjustPoints, setAdjustPoints] = useState<number>(100);
  const [adjustReason, setAdjustReason] = useState('');
  const [adjustNotes, setAdjustNotes] = useState('');

  // Campaign Modal State
  const [campaignModalOpen, setCampaignModalOpen] = useState(false);
  const [editingCampaign, setEditingCampaign] = useState<LoyaltyCampaign | null>(null);
  const [campName, setCampName] = useState('');
  const [campType, setCampType] = useState('DOUBLE_POINTS');
  const [campMultiplier, setCampMultiplier] = useState(2.0);
  const [campBonus, setCampBonus] = useState(0);
  const [campStartDate, setCampStartDate] = useState('');
  const [campEndDate, setCampEndDate] = useState('');
  const [campIsActive, setCampIsActive] = useState(true);

  // Settings State Form
  const [formConfig, setFormConfig] = useState<LoyaltyProgramConfig | null>(null);

  // Fetch functions
  const fetchStats = useCallback(async () => {
    try {
      const res = await api.get<LoyaltyAnalytics>('/loyalty/admin/stats');
      setStats(res);
    } catch {}
  }, []);

  const fetchConfig = useCallback(async () => {
    try {
      const res = await api.get<LoyaltyProgramConfig>('/loyalty/admin/config');
      setConfig(res);
      setFormConfig(res);
    } catch {}
  }, []);

  const fetchMembers = useCallback(async () => {
    try {
      const url = searchQuery ? `/loyalty/admin/members?search=${encodeURIComponent(searchQuery)}` : '/loyalty/admin/members';
      const res = await api.get<LoyaltyMemberSummary[]>(url);
      const customerOnly = Array.isArray(res)
        ? res.filter((m) => !m.role || m.role.toUpperCase() === 'CUSTOMER')
        : [];
      setMembers(customerOnly);
    } catch {}
  }, [searchQuery]);

  const fetchCampaigns = useCallback(async () => {
    try {
      const res = await api.get<LoyaltyCampaign[]>('/loyalty/admin/campaigns');
      setCampaigns(res);
    } catch {}
  }, []);

  const fetchMilestones = useCallback(async () => {
    try {
      const res = await api.get<LoyaltyMilestone[]>('/loyalty/admin/milestones');
      setMilestones(res);
    } catch {}
  }, []);

  const fetchTransactions = useCallback(async () => {
    try {
      const url = txTypeFilter !== 'ALL' ? `/loyalty/admin/transactions?type=${encodeURIComponent(txTypeFilter)}` : '/loyalty/admin/transactions';
      const res = await api.get<LoyaltyTransaction[]>(url);
      setTransactions(res);
    } catch {}
  }, [txTypeFilter]);

  const loadAllData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      await Promise.all([
        fetchStats(),
        fetchConfig(),
        fetchMembers(),
        fetchCampaigns(),
        fetchMilestones(),
        fetchTransactions()
      ]);
    } catch (err: any) {
      setError(err?.message || 'Failed to load loyalty dashboard');
    } finally {
      setLoading(false);
    }
  }, [fetchStats, fetchConfig, fetchMembers, fetchCampaigns, fetchMilestones, fetchTransactions]);

  useEffect(() => {
    loadAllData();
  }, [loadAllData]);

  // Adjust Points Handlers
  const handleOpenAdjustModal = (member: LoyaltyMemberSummary) => {
    if (member.role && member.role.toUpperCase() !== 'CUSTOMER') {
      setError('Loyalty points can only be adjusted for customer accounts.');
      return;
    }
    setSelectedMember(member);
    setAdjustType('CREDIT');
    setAdjustPoints(100);
    setAdjustReason('');
    setAdjustNotes('');
    setAdjustModalOpen(true);
  };

  const handleSubmitAdjustment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedMember) return;
    if (!adjustReason || adjustReason.trim().length < 3) {
      setError('Audit Reason is mandatory and must be at least 3 characters.');
      return;
    }
    if (adjustPoints <= 0) {
      setError('Points amount must be greater than zero.');
      return;
    }

    const delta = adjustType === 'CREDIT' ? Math.abs(adjustPoints) : -Math.abs(adjustPoints);
    if (adjustType === 'DEBIT' && selectedMember.available_points < Math.abs(delta)) {
      setError(`Cannot deduct ${Math.abs(delta).toLocaleString()} points. Customer only has ${selectedMember.available_points.toLocaleString()} points.`);
      return;
    }

    setActionLoading(true);
    setError(null);
    try {
      await api.post('/loyalty/admin/adjust-points', {
        user_id: selectedMember.user_id,
        points_delta: delta,
        reason: adjustReason.trim(),
        admin_notes: adjustNotes.trim() || undefined
      });
      setSuccessMsg(`Successfully adjusted ${delta > 0 ? '+' : ''}${delta.toLocaleString()} points for ${selectedMember.full_name}.`);
      setAdjustModalOpen(false);
      await Promise.all([fetchMembers(), fetchStats(), fetchTransactions()]);
    } catch (err: any) {
      setError(err?.message || 'Failed to adjust points.');
    } finally {
      setActionLoading(false);
    }
  };

  // Campaign Handlers
  const handleOpenCampaignModal = (camp?: LoyaltyCampaign) => {
    if (camp) {
      setEditingCampaign(camp);
      setCampName(camp.name);
      setCampType(camp.campaign_type);
      setCampMultiplier(camp.multiplier);
      setCampBonus(camp.bonus_points);
      setCampStartDate(camp.start_date ? camp.start_date.substring(0, 10) : '');
      setCampEndDate(camp.end_date ? camp.end_date.substring(0, 10) : '');
      setCampIsActive(camp.is_active);
    } else {
      setEditingCampaign(null);
      setCampName('');
      setCampType('DOUBLE_POINTS');
      setCampMultiplier(2.0);
      setCampBonus(0);
      setCampStartDate('');
      setCampEndDate('');
      setCampIsActive(true);
    }
    setCampaignModalOpen(true);
  };

  const handleSaveCampaign = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!campName.trim()) {
      setError('Campaign name is required.');
      return;
    }

    setActionLoading(true);
    setError(null);
    try {
      const payload = {
        name: campName.trim(),
        campaign_type: campType,
        multiplier: Number(campMultiplier) || 1.0,
        bonus_points: Number(campBonus) || 0,
        start_date: campStartDate ? new Date(campStartDate).toISOString() : undefined,
        end_date: campEndDate ? new Date(campEndDate).toISOString() : undefined,
        is_active: campIsActive
      };

      if (editingCampaign) {
        await api.put(`/loyalty/admin/campaigns/${editingCampaign.id}`, payload);
        setSuccessMsg(`Updated campaign "${campName}".`);
      } else {
        await api.post('/loyalty/admin/campaigns', payload);
        setSuccessMsg(`Created campaign "${campName}".`);
      }
      setCampaignModalOpen(false);
      await Promise.all([fetchCampaigns(), fetchStats()]);
    } catch (err: any) {
      setError(err?.message || 'Failed to save campaign.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeleteCampaign = async (id: string, name: string) => {
    if (!window.confirm(`Are you sure you want to delete campaign "${name}"?`)) return;
    setActionLoading(true);
    try {
      await api.delete(`/loyalty/admin/campaigns/${id}`);
      setSuccessMsg(`Deleted campaign "${name}".`);
      await Promise.all([fetchCampaigns(), fetchStats()]);
    } catch (err: any) {
      setError(err?.message || 'Failed to delete campaign.');
    } finally {
      setActionLoading(false);
    }
  };

  // Toggle Program Active Switch
  const handleToggleProgramStatus = async () => {
    if (!config) return;
    const newStatus = !config.is_enabled;
    setActionLoading(true);
    try {
      const updated = await api.put<LoyaltyProgramConfig>('/loyalty/admin/config', {
        ...config,
        is_enabled: newStatus
      });
      setConfig(updated);
      setFormConfig(updated);
      setSuccessMsg(`Loyalty programme is now ${newStatus ? 'ENABLED' : 'PAUSED'}.`);
      await fetchStats();
    } catch (err: any) {
      setError(err?.message || 'Failed to toggle programme status.');
    } finally {
      setActionLoading(false);
    }
  };

  // Save Program Settings
  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formConfig) return;

    setActionLoading(true);
    setError(null);
    try {
      const updated = await api.put<LoyaltyProgramConfig>('/loyalty/admin/config', {
        is_enabled: formConfig.is_enabled,
        earning_rate_pence_per_point: Number(formConfig.earning_rate_pence_per_point),
        points_per_pound_reward: Number(formConfig.points_per_pound_reward),
        min_redemption_points: Number(formConfig.min_redemption_points),
        redemption_increment_points: Number(formConfig.redemption_increment_points)
      });
      setConfig(updated);
      setFormConfig(updated);
      setSuccessMsg('Loyalty programme configuration successfully saved and published!');
    } catch (err: any) {
      setError(err?.message || 'Failed to save configuration.');
    } finally {
      setActionLoading(false);
    }
  };

  const getTxBadge = (type: string) => {
    const t = type.toUpperCase();
    if (t.includes('DOUBLE') || t.includes('TRIPLE') || t === 'BONUS') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-[#FF5500]/20 text-[#FF5500] border border-[#FF5500]/40">
          <Zap className="w-2.5 h-2.5" />
          {t}
        </span>
      );
    }
    if (t === 'EARN' || t === 'EARNED') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-[#22C55E]/15 text-[#22C55E] border border-[#22C55E]/30">
          <CheckCircle2 className="w-2.5 h-2.5" />
          EARN
        </span>
      );
    }
    if (t === 'REDEEM' || t === 'REDEEMED') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-[#3B82F6]/15 text-[#60A5FA] border border-[#3B82F6]/30">
          <Gift className="w-2.5 h-2.5" />
          REDEEM
        </span>
      );
    }
    if (t.includes('REVERSE') || t.includes('REFUND')) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-[#EF4444]/15 text-[#F87171] border border-[#EF4444]/30">
          <RotateCcw className="w-2.5 h-2.5" />
          {t}
        </span>
      );
    }
    if (t === 'MANUAL_CREDIT') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-[#10B981]/15 text-[#34D399] border border-[#10B981]/30">
          + CREDIT
        </span>
      );
    }
    if (t === 'MANUAL_DEBIT') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-[#F59E0B]/15 text-[#FBBF24] border border-[#F59E0B]/30">
          - DEBIT
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-[#374151]/40 text-[#D1D5DB] border border-[#4B5563]/40">
        {t}
      </span>
    );
  };

  return (
    <div className="w-full max-w-[1300px] mx-auto px-4 sm:px-8 py-8 space-y-8 text-[#F5F5F5] pb-24">
      {/* Top Header Row */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-[#242424]">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-extrabold uppercase bg-[#FF5500]/15 text-[#FF5500] border border-[#FF5500]/30">
              Super Admin
            </span>
            <span className="text-xs text-[#9CA3AF] font-medium">Patty Points Engine</span>
          </div>
          <h1 className="text-3xl font-extrabold text-white tracking-tight mt-1">
            Loyalty Programme Management
          </h1>
          <p className="text-xs text-[#A1A1AA] mt-1 max-w-2xl">
            Authoritative controls for 1p = 1pt earning rates, 4,000-point first redemption milestones, campaign multipliers, member points adjustment, and full audit ledgers.
          </p>
        </div>

        {/* Master Programme Switch */}
        <div className="flex items-center gap-3 bg-[#121212] border border-[#242424] p-3.5 rounded-2xl shrink-0">
          <div className="text-right">
            <p className="text-xs font-extrabold text-white">Programme Status</p>
            <p className={`text-[11px] font-bold ${config?.is_enabled ? 'text-[#22C55E]' : 'text-[#EF4444]'}`}>
              {config?.is_enabled ? 'Active & Earning' : 'Paused'}
            </p>
          </div>
          <button
            onClick={handleToggleProgramStatus}
            disabled={actionLoading}
            className={`w-12 h-6 flex items-center rounded-full p-1 transition-colors duration-300 cursor-pointer ${
              config?.is_enabled ? 'bg-[#22C55E]' : 'bg-[#374151]'
            }`}
          >
            <div
              className={`bg-white w-4 h-4 rounded-full shadow-md transform transition-transform duration-300 ${
                config?.is_enabled ? 'translate-x-6' : 'translate-x-0'
              }`}
            />
          </button>
        </div>
      </div>

      {/* Notifications */}
      {error && (
        <div className="p-4 bg-[#2A1215] border border-[#EF4444]/40 rounded-xl flex items-center justify-between gap-3 text-xs text-[#FCA5A5]">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-[#EF4444] shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-xs text-[#FCA5A5] hover:text-white font-bold">
            Dismiss
          </button>
        </div>
      )}

      {successMsg && (
        <div className="p-4 bg-[#0F291E] border border-[#22C55E]/40 rounded-xl flex items-center justify-between gap-3 text-xs text-[#86EFAC]">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-[#22C55E] shrink-0" />
            <span>{successMsg}</span>
          </div>
          <button onClick={() => setSuccessMsg(null)} className="text-xs text-[#86EFAC] hover:text-white font-bold">
            Dismiss
          </button>
        </div>
      )}

      {/* Analytics KPI Metric Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <div className="bg-[#121212] border border-[#222222] rounded-2xl p-4.5 flex flex-col justify-between shadow-md">
          <span className="text-[11px] font-extrabold uppercase tracking-wider text-[#9CA3AF]">
            Total Members
          </span>
          <div className="text-2xl font-black text-white mt-2">
            {stats?.total_members?.toLocaleString() ?? 0}
          </div>
          <span className="text-[10px] text-[#71717A] mt-1">Registered customers</span>
        </div>

        <div className="bg-[#121212] border border-[#FF5500]/30 rounded-2xl p-4.5 flex flex-col justify-between shadow-md relative overflow-hidden">
          <div className="absolute top-0 right-0 w-20 h-20 bg-[#FF5500]/5 rounded-full blur-xl pointer-events-none" />
          <span className="text-[11px] font-extrabold uppercase tracking-wider text-[#FF5500]">
            Active Balance
          </span>
          <div className="text-2xl font-black text-[#FF5500] mt-2">
            {stats?.total_active_points?.toLocaleString() ?? 0} <span className="text-xs text-white">PTS</span>
          </div>
          <span className="text-[10px] text-[#D1D5DB] mt-1">
            Liability: £{stats?.total_outstanding_liability_pounds?.toFixed(2) ?? '0.00'}
          </span>
        </div>

        <div className="bg-[#121212] border border-[#222222] rounded-2xl p-4.5 flex flex-col justify-between shadow-md">
          <span className="text-[11px] font-extrabold uppercase tracking-wider text-[#22C55E]">
            Issued Points
          </span>
          <div className="text-2xl font-black text-[#22C55E] mt-2">
            {stats?.total_points_issued?.toLocaleString() ?? 0}
          </div>
          <span className="text-[10px] text-[#71717A] mt-1">
            Value: £{stats?.total_reward_value_issued?.toFixed(2) ?? '0.00'}
          </span>
        </div>

        <div className="bg-[#121212] border border-[#222222] rounded-2xl p-4.5 flex flex-col justify-between shadow-md">
          <span className="text-[11px] font-extrabold uppercase tracking-wider text-[#60A5FA]">
            Redeemed
          </span>
          <div className="text-2xl font-black text-[#60A5FA] mt-2">
            {stats?.total_points_redeemed?.toLocaleString() ?? 0}
          </div>
          <span className="text-[10px] text-[#71717A] mt-1">
            Claimed: £{stats?.total_reward_value_redeemed?.toFixed(2) ?? '0.00'}
          </span>
        </div>

        <div className="bg-[#121212] border border-[#222222] rounded-2xl p-4.5 flex flex-col justify-between shadow-md">
          <span className="text-[11px] font-extrabold uppercase tracking-wider text-[#F87171]">
            Reversed
          </span>
          <div className="text-2xl font-black text-[#F87171] mt-2">
            {stats?.total_points_reversed?.toLocaleString() ?? 0}
          </div>
          <span className="text-[10px] text-[#71717A] mt-1">Cancelled & refunds</span>
        </div>

        <div className="bg-[#121212] border border-[#222222] rounded-2xl p-4.5 flex flex-col justify-between shadow-md">
          <span className="text-[11px] font-extrabold uppercase tracking-wider text-[#FFA000]">
            Campaigns
          </span>
          <div className="text-2xl font-black text-[#FFA000] mt-2">
            {stats?.active_campaigns_count ?? 0}
          </div>
          <span className="text-[10px] text-[#71717A] mt-1">Active promotions</span>
        </div>
      </div>

      {/* Tabs Navigation */}
      <div className="flex items-center gap-2 border-b border-[#242424] overflow-x-auto pb-1">
        <button
          onClick={() => setActiveTab('members')}
          className={`flex items-center gap-2 px-5 py-3 text-xs font-extrabold rounded-t-xl transition-all whitespace-nowrap cursor-pointer ${
            activeTab === 'members'
              ? 'bg-[#1E1E1E] text-[#FF5500] border-t-2 border-[#FF5500]'
              : 'text-[#9CA3AF] hover:text-white hover:bg-[#151515]'
          }`}
        >
          <Users className="w-4 h-4" />
          <span>Members & Balances</span>
        </button>

        <button
          onClick={() => setActiveTab('campaigns')}
          className={`flex items-center gap-2 px-5 py-3 text-xs font-extrabold rounded-t-xl transition-all whitespace-nowrap cursor-pointer ${
            activeTab === 'campaigns'
              ? 'bg-[#1E1E1E] text-[#FF5500] border-t-2 border-[#FF5500]'
              : 'text-[#9CA3AF] hover:text-white hover:bg-[#151515]'
          }`}
        >
          <Zap className="w-4 h-4" />
          <span>Promotions & Multipliers</span>
        </button>

        <button
          onClick={() => setActiveTab('milestones')}
          className={`flex items-center gap-2 px-5 py-3 text-xs font-extrabold rounded-t-xl transition-all whitespace-nowrap cursor-pointer ${
            activeTab === 'milestones'
              ? 'bg-[#1E1E1E] text-[#FF5500] border-t-2 border-[#FF5500]'
              : 'text-[#9CA3AF] hover:text-white hover:bg-[#151515]'
          }`}
        >
          <Award className="w-4 h-4" />
          <span>Milestones</span>
        </button>

        <button
          onClick={() => setActiveTab('transactions')}
          className={`flex items-center gap-2 px-5 py-3 text-xs font-extrabold rounded-t-xl transition-all whitespace-nowrap cursor-pointer ${
            activeTab === 'transactions'
              ? 'bg-[#1E1E1E] text-[#FF5500] border-t-2 border-[#FF5500]'
              : 'text-[#9CA3AF] hover:text-white hover:bg-[#151515]'
          }`}
        >
          <Clock className="w-4 h-4" />
          <span>Audit & Ledger</span>
        </button>

        <button
          onClick={() => setActiveTab('settings')}
          className={`flex items-center gap-2 px-5 py-3 text-xs font-extrabold rounded-t-xl transition-all whitespace-nowrap cursor-pointer ${
            activeTab === 'settings'
              ? 'bg-[#1E1E1E] text-[#FF5500] border-t-2 border-[#FF5500]'
              : 'text-[#9CA3AF] hover:text-white hover:bg-[#151515]'
          }`}
        >
          <Settings className="w-4 h-4" />
          <span>Programme Rules</span>
        </button>
      </div>

      {/* ============================================================ */}
      {/* TAB 1: MEMBERS */}
      {/* ============================================================ */}
      {activeTab === 'members' && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-[#121212] border border-[#242424] p-3 rounded-2xl">
            <div className="relative w-full sm:w-80">
              <Search className="w-4 h-4 absolute left-3.5 top-3 text-[#71717A]" />
              <input
                type="text"
                placeholder="Search by name, email, or phone..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && fetchMembers()}
                className="w-full h-10 bg-[#1A1A1A] border border-[#2E2E2E] focus:border-[#FF5500] rounded-xl pl-10 pr-3.5 text-xs text-white placeholder-[#71717A] focus:outline-none"
              />
            </div>
            <button
              onClick={fetchMembers}
              className="flex items-center gap-1.5 px-4 py-2 bg-[#1E1E1E] hover:bg-[#2A2A2A] text-xs font-bold text-white rounded-xl border border-[#333333] transition-colors cursor-pointer"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Refresh Members</span>
            </button>
          </div>

          <div className="bg-[#121212] border border-[#242424] rounded-2xl overflow-hidden shadow-xl">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="bg-[#171717] text-[#9CA3AF] uppercase text-[11px] font-semibold border-b border-[#242424]">
                  <tr>
                    <th className="px-6 py-4">Customer</th>
                    <th className="px-6 py-4">Phone</th>
                    <th className="px-6 py-4 text-right">Available Points</th>
                    <th className="px-6 py-4 text-right">Reward Value</th>
                    <th className="px-6 py-4 text-center">Redemption Status</th>
                    <th className="px-6 py-4 text-right">Earned / Redeemed</th>
                    <th className="px-6 py-4 text-center">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1F1F1F]">
                  {members.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-6 py-12 text-center text-[#71717A]">
                        No loyalty members found.
                      </td>
                    </tr>
                  ) : (
                    members.map((m) => (
                      <tr key={m.user_id} className="hover:bg-[#181818] transition-colors">
                        <td className="px-6 py-4">
                          <p className="font-extrabold text-white text-sm">{m.full_name}</p>
                          <p className="text-[11px] text-[#9CA3AF]">{m.email}</p>
                        </td>
                        <td className="px-6 py-4 text-[#A1A1AA]">{m.phone || '-'}</td>
                        <td className="px-6 py-4 text-right font-black text-[#FF5500] text-sm whitespace-nowrap">
                          {m.available_points.toLocaleString()} PTS
                        </td>
                        <td className="px-6 py-4 text-right font-bold text-white whitespace-nowrap">
                          £{m.reward_value.toFixed(2)}
                        </td>
                        <td className="px-6 py-4 text-center">
                          {m.is_redemption_eligible ? (
                            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-[#22C55E]/15 text-[#22C55E] border border-[#22C55E]/30">
                              <CheckCircle2 className="w-2.5 h-2.5" />
                              Unlocked (&gt;= 4,000)
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-[#374151]/40 text-[#9CA3AF] border border-[#4B5563]/30">
                              Under 4,000 PTS
                            </span>
                          )}
                        </td>
                        <td className="px-6 py-4 text-right text-[11px] text-[#9CA3AF] whitespace-nowrap">
                          <span className="text-[#22C55E]">+{m.lifetime_points.toLocaleString()}</span> /{' '}
                          <span className="text-[#60A5FA]">-{m.total_redeemed.toLocaleString()}</span>
                        </td>
                        <td className="px-6 py-4 text-center">
                          {(!m.role || m.role.toUpperCase() === 'CUSTOMER') && (
                            <button
                              onClick={() => handleOpenAdjustModal(m)}
                              className="px-3 py-1.5 bg-[#FF5500]/10 hover:bg-[#FF5500] text-[#FF5500] hover:text-white border border-[#FF5500]/40 rounded-xl text-xs font-bold transition-all cursor-pointer"
                            >
                              Adjust Points
                            </button>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* TAB 2: CAMPAIGNS & MULTIPLIERS */}
      {/* ============================================================ */}
      {activeTab === 'campaigns' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between bg-[#121212] border border-[#242424] p-4 rounded-2xl">
            <div>
              <h3 className="text-sm font-extrabold text-white">Promotional Loyalty Campaigns</h3>
              <p className="text-xs text-[#9CA3AF]">
                Configure Double Points, Triple Points, or bonus points campaigns with date windows.
              </p>
            </div>
            <button
              onClick={() => handleOpenCampaignModal()}
              className="flex items-center gap-1.5 px-4 py-2.5 bg-[#FF5500] hover:bg-[#E84F00] text-white text-xs font-bold rounded-xl shadow-lg shadow-[#FF5500]/20 transition-all cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              <span>New Campaign</span>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {campaigns.length === 0 ? (
              <div className="col-span-full p-12 text-center text-xs text-[#71717A] bg-[#121212] border border-[#242424] rounded-2xl">
                No promotional campaigns created yet. Click "+ New Campaign" to launch one.
              </div>
            ) : (
              campaigns.map((camp) => (
                <div
                  key={camp.id}
                  className="bg-[#121212] border border-[#242424] hover:border-[#FF5500]/40 rounded-2xl p-5 space-y-4 transition-all shadow-lg flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="px-2.5 py-0.5 rounded text-[10px] font-extrabold uppercase bg-[#FF5500]/15 text-[#FF5500] border border-[#FF5500]/30">
                        {camp.campaign_type}
                      </span>
                      <span
                        className={`inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded ${
                          camp.is_active
                            ? 'bg-[#22C55E]/15 text-[#22C55E] border border-[#22C55E]/30'
                            : 'bg-[#374151]/40 text-[#9CA3AF] border border-[#4B5563]/30'
                        }`}
                      >
                        {camp.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                    <h4 className="text-base font-extrabold text-white">{camp.name}</h4>
                    <div className="mt-3 p-3 bg-[#1A1A1A] rounded-xl space-y-1 text-xs">
                      <div className="flex justify-between text-[#9CA3AF]">
                        <span>Points Multiplier:</span>
                        <span className="font-extrabold text-[#FF5500]">{camp.multiplier}x</span>
                      </div>
                      {camp.bonus_points > 0 && (
                        <div className="flex justify-between text-[#9CA3AF]">
                          <span>Bonus Points:</span>
                          <span className="font-bold text-white">+{camp.bonus_points} PTS</span>
                        </div>
                      )}
                      <div className="flex justify-between text-[#9CA3AF] pt-1 border-t border-[#282828]">
                        <span>Valid:</span>
                        <span className="text-white">
                          {camp.start_date ? new Date(camp.start_date).toLocaleDateString('en-GB') : 'Immediate'}
                          {' → '}
                          {camp.end_date ? new Date(camp.end_date).toLocaleDateString('en-GB') : 'No expiry'}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-end gap-2 pt-2 border-t border-[#222222]">
                    <button
                      onClick={() => handleOpenCampaignModal(camp)}
                      className="p-2 text-[#A1A1AA] hover:text-white bg-[#1A1A1A] hover:bg-[#282828] rounded-lg transition-colors cursor-pointer"
                      title="Edit Campaign"
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => handleDeleteCampaign(camp.id, camp.name)}
                      className="p-2 text-[#EF4444] hover:text-white bg-[#EF4444]/10 hover:bg-[#EF4444] rounded-lg transition-colors cursor-pointer"
                      title="Delete Campaign"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* TAB 3: MILESTONES */}
      {/* ============================================================ */}
      {activeTab === 'milestones' && (
        <div className="space-y-4">
          <div className="bg-[#121212] border border-[#242424] p-5 rounded-2xl">
            <h3 className="text-sm font-extrabold text-white">Configurable Milestones Architecture</h3>
            <p className="text-xs text-[#9CA3AF] mt-1">
              The authoritative business specification defines the <strong>4,000-point threshold</strong> as the primary First Redemption Milestone.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {milestones.map((m) => (
              <div key={m.milestone_id} className="bg-[#121212] border border-[#FF5500]/30 rounded-2xl p-6 space-y-4 shadow-xl">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="w-9 h-9 rounded-xl bg-[#FF5500]/10 border border-[#FF5500]/30 flex items-center justify-center text-[#FF5500]">
                      <Award className="w-5 h-5" />
                    </div>
                    <div>
                      <h4 className="font-extrabold text-white text-base">{m.milestone_name}</h4>
                      <p className="text-xs text-[#9CA3AF]">{m.description || 'Core first redemption milestone'}</p>
                    </div>
                  </div>
                  <span className="px-2.5 py-0.5 rounded text-[10px] font-extrabold uppercase bg-[#22C55E]/15 text-[#22C55E] border border-[#22C55E]/30">
                    Active
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3 pt-3 border-t border-[#222222] text-xs">
                  <div className="p-3 bg-[#1A1A1A] rounded-xl">
                    <span className="text-[#9CA3AF] block text-[11px]">Threshold Points</span>
                    <span className="text-lg font-extrabold text-white">
                      {(m.points_required || 4000).toLocaleString()} PTS
                    </span>
                  </div>
                  <div className="p-3 bg-[#1A1A1A] rounded-xl">
                    <span className="text-[#9CA3AF] block text-[11px]">Standard Reward Value</span>
                    <span className="text-lg font-extrabold text-[#22C55E]">
                      £{(m.reward_value || 4.0).toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* TAB 4: AUDIT & TRANSACTIONS LEDGER */}
      {/* ============================================================ */}
      {activeTab === 'transactions' && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-[#121212] border border-[#242424] p-3 rounded-2xl">
            <div className="flex items-center gap-2 w-full sm:w-auto">
              <span className="text-xs text-[#9CA3AF] font-bold">Filter Type:</span>
              <select
                value={txTypeFilter}
                onChange={(e) => setTxTypeFilter(e.target.value)}
                className="h-10 bg-[#1A1A1A] border border-[#2E2E2E] focus:border-[#FF5500] rounded-xl px-3 text-xs text-white focus:outline-none cursor-pointer"
              >
                <option value="ALL">All Transactions</option>
                <option value="EARN">EARNED</option>
                <option value="REDEEM">REDEEMED</option>
                <option value="DOUBLE_POINTS">DOUBLE_POINTS</option>
                <option value="TRIPLE_POINTS">TRIPLE_POINTS</option>
                <option value="BONUS">BONUS</option>
                <option value="REVERSE">REVERSED / REFUNDED</option>
                <option value="MANUAL_CREDIT">MANUAL_CREDIT</option>
                <option value="MANUAL_DEBIT">MANUAL_DEBIT</option>
              </select>
            </div>
            <button
              onClick={fetchTransactions}
              className="flex items-center gap-1.5 px-4 py-2 bg-[#1E1E1E] hover:bg-[#2A2A2A] text-xs font-bold text-white rounded-xl border border-[#333333] transition-colors cursor-pointer"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Refresh Ledger</span>
            </button>
          </div>

          <div className="bg-[#121212] border border-[#242424] rounded-2xl overflow-hidden shadow-xl">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="bg-[#171717] text-[#9CA3AF] uppercase text-[11px] font-semibold border-b border-[#242424]">
                  <tr>
                    <th className="px-6 py-4">Timestamp</th>
                    <th className="px-6 py-4">Type</th>
                    <th className="px-6 py-4">Activity / Audit Reason</th>
                    <th className="px-6 py-4 text-right">Points Delta</th>
                    <th className="px-6 py-4 text-right">Resulting Balance</th>
                    <th className="px-6 py-4">Admin / Origin</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1F1F1F]">
                  {transactions.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-6 py-12 text-center text-[#71717A]">
                        No loyalty transactions found.
                      </td>
                    </tr>
                  ) : (
                    transactions.map((tx) => {
                      const isPositive = tx.points > 0;
                      return (
                        <tr key={tx.id} className="hover:bg-[#181818] transition-colors">
                          <td className="px-6 py-4 text-[#9CA3AF] whitespace-nowrap">
                            {new Date(tx.created_at).toLocaleDateString('en-GB', {
                              day: '2-digit',
                              month: 'short',
                              year: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit'
                            })}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">{getTxBadge(tx.transaction_type)}</td>
                          <td className="px-6 py-4 text-white font-medium max-w-sm truncate">
                            {tx.description || '-'}
                          </td>
                          <td className="px-6 py-4 text-right font-black whitespace-nowrap">
                            <span className={isPositive ? 'text-[#22C55E]' : 'text-[#EF4444]'}>
                              {isPositive ? `+${tx.points.toLocaleString()}` : tx.points.toLocaleString()} PTS
                            </span>
                          </td>
                          <td className="px-6 py-4 text-right text-[#D1D5DB] font-bold whitespace-nowrap">
                            {tx.resulting_balance !== undefined && tx.resulting_balance !== null
                              ? `${tx.resulting_balance.toLocaleString()} PTS`
                              : '-'}
                          </td>
                          <td className="px-6 py-4 text-[#9CA3AF] text-[11px] whitespace-nowrap">
                            {tx.admin_email || 'System / Order'}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* TAB 5: PROGRAMME RULES & CONFIGURATION */}
      {/* ============================================================ */}
      {activeTab === 'settings' && formConfig && (
        <form onSubmit={handleSaveSettings} className="space-y-6 max-w-3xl">
          <div className="bg-[#121212] border border-[#242424] rounded-2xl p-6 sm:p-8 space-y-6 shadow-xl">
            <div>
              <h3 className="text-base font-extrabold text-white flex items-center gap-2">
                <Sliders className="w-5 h-5 text-[#FF5500]" />
                Authoritative Loyalty Programme Rules
              </h3>
              <p className="text-xs text-[#9CA3AF] mt-1">
                Configure earning rate, redemption increments, and milestone thresholds. All modifications persist to PostgreSQL.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 pt-4 border-t border-[#222222]">
              <div>
                <label className="block text-xs font-bold text-white mb-1.5">
                  Earning Rate (Pence per Point)
                </label>
                <input
                  type="number"
                  min="1"
                  value={formConfig.earning_rate_pence_per_point}
                  onChange={(e) =>
                    setFormConfig({ ...formConfig, earning_rate_pence_per_point: Number(e.target.value) })
                  }
                  className="w-full h-11 bg-[#1A1A1A] border border-[#2E2E2E] focus:border-[#FF5500] rounded-xl px-3.5 text-xs text-white focus:outline-none"
                  required
                />
                <p className="text-[11px] text-[#9CA3AF] mt-1">1p spend = 1 Patty Point (£1.00 = 100 PTS)</p>
              </div>

              <div>
                <label className="block text-xs font-bold text-white mb-1.5">
                  Points per £1.00 Reward Discount
                </label>
                <input
                  type="number"
                  min="100"
                  step="100"
                  value={formConfig.points_per_pound_reward}
                  onChange={(e) =>
                    setFormConfig({ ...formConfig, points_per_pound_reward: Number(e.target.value) })
                  }
                  className="w-full h-11 bg-[#1A1A1A] border border-[#2E2E2E] focus:border-[#FF5500] rounded-xl px-3.5 text-xs text-white focus:outline-none"
                  required
                />
                <p className="text-[11px] text-[#9CA3AF] mt-1">1,000 points = £1.00 (10% reward value)</p>
              </div>

              <div>
                <label className="block text-xs font-bold text-white mb-1.5">
                  Minimum Redemption Threshold (Points)
                </label>
                <input
                  type="number"
                  min="1000"
                  step="1000"
                  value={formConfig.min_redemption_points}
                  onChange={(e) =>
                    setFormConfig({ ...formConfig, min_redemption_points: Number(e.target.value) })
                  }
                  className="w-full h-11 bg-[#1A1A1A] border border-[#2E2E2E] focus:border-[#FF5500] rounded-xl px-3.5 text-xs text-white focus:outline-none"
                  required
                />
                <p className="text-[11px] text-[#9CA3AF] mt-1">Minimum 4,000 points (£4.00) required to redeem</p>
              </div>

              <div>
                <label className="block text-xs font-bold text-white mb-1.5">
                  Redemption Increment (Points)
                </label>
                <input
                  type="number"
                  min="500"
                  step="500"
                  value={formConfig.redemption_increment_points}
                  onChange={(e) =>
                    setFormConfig({ ...formConfig, redemption_increment_points: Number(e.target.value) })
                  }
                  className="w-full h-11 bg-[#1A1A1A] border border-[#2E2E2E] focus:border-[#FF5500] rounded-xl px-3.5 text-xs text-white focus:outline-none"
                  required
                />
                <p className="text-[11px] text-[#9CA3AF] mt-1">Redeem in whole 1,000-point (£1) steps only</p>
              </div>
            </div>

            <div className="pt-4 border-t border-[#222222] flex items-center justify-between">
              <div className="text-xs text-[#9CA3AF]">
                Last updated: {config?.updated_at ? new Date(config.updated_at).toLocaleString('en-GB') : 'Default'}
              </div>
              <button
                type="submit"
                disabled={actionLoading}
                className="px-6 py-3 bg-[#FF5500] hover:bg-[#E84F00] text-white text-xs font-extrabold rounded-xl shadow-lg shadow-[#FF5500]/25 transition-all cursor-pointer disabled:opacity-50"
              >
                {actionLoading ? 'Saving...' : 'Save & Publish Rules'}
              </button>
            </div>
          </div>
        </form>
      )}

      {/* ============================================================ */}
      {/* MODAL: MANUAL POINTS ADJUSTMENT */}
      {/* ============================================================ */}
      {adjustModalOpen && selectedMember && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
          <div className="bg-[#121212] border border-[#2E2E2E] rounded-2xl max-w-md w-full p-6 space-y-5 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-[#242424]">
              <div>
                <h3 className="text-base font-extrabold text-white">Manual Point Adjustment</h3>
                <p className="text-xs text-[#9CA3AF]">{selectedMember.full_name} ({selectedMember.email})</p>
              </div>
              <button
                onClick={() => setAdjustModalOpen(false)}
                className="text-[#9CA3AF] hover:text-white p-1"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSubmitAdjustment} className="space-y-4">
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setAdjustType('CREDIT')}
                  className={`flex-1 py-2.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                    adjustType === 'CREDIT'
                      ? 'bg-[#22C55E] text-white shadow-md'
                      : 'bg-[#1A1A1A] text-[#9CA3AF] border border-[#2E2E2E]'
                  }`}
                >
                  + Credit (Add Points)
                </button>
                <button
                  type="button"
                  onClick={() => setAdjustType('DEBIT')}
                  className={`flex-1 py-2.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                    adjustType === 'DEBIT'
                      ? 'bg-[#EF4444] text-white shadow-md'
                      : 'bg-[#1A1A1A] text-[#9CA3AF] border border-[#2E2E2E]'
                  }`}
                >
                  - Debit (Deduct Points)
                </button>
              </div>

              <div>
                <label className="block text-xs font-bold text-white mb-1">
                  Points Amount <span className="text-[#FF5500]">*</span>
                </label>
                <input
                  type="number"
                  min="1"
                  value={adjustPoints}
                  onChange={(e) => setAdjustPoints(Number(e.target.value))}
                  className="w-full h-11 bg-[#1A1A1A] border border-[#2E2E2E] focus:border-[#FF5500] rounded-xl px-3.5 text-xs text-white focus:outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-white mb-1">
                  Audit Reason (Mandatory) <span className="text-[#FF5500]">*</span>
                </label>
                <input
                  type="text"
                  placeholder="e.g. Customer goodwill resolution for delayed order #1042"
                  value={adjustReason}
                  onChange={(e) => setAdjustReason(e.target.value)}
                  className="w-full h-11 bg-[#1A1A1A] border border-[#2E2E2E] focus:border-[#FF5500] rounded-xl px-3.5 text-xs text-white focus:outline-none"
                  required
                />
                <p className="text-[11px] text-[#9CA3AF] mt-1">Recorded in the immutable transaction ledger.</p>
              </div>

              <div>
                <label className="block text-xs font-bold text-white mb-1">
                  Internal Notes (Optional)
                </label>
                <textarea
                  rows={2}
                  placeholder="Additional context for staff..."
                  value={adjustNotes}
                  onChange={(e) => setAdjustNotes(e.target.value)}
                  className="w-full bg-[#1A1A1A] border border-[#2E2E2E] focus:border-[#FF5500] rounded-xl p-3 text-xs text-white focus:outline-none"
                />
              </div>

              <div className="p-3 bg-[#171717] rounded-xl text-xs space-y-1">
                <div className="flex justify-between text-[#9CA3AF]">
                  <span>Current Balance:</span>
                  <span className="font-bold text-white">{selectedMember.available_points.toLocaleString()} PTS</span>
                </div>
                <div className="flex justify-between text-[#9CA3AF]">
                  <span>Adjustment:</span>
                  <span className={`font-bold ${adjustType === 'CREDIT' ? 'text-[#22C55E]' : 'text-[#EF4444]'}`}>
                    {adjustType === 'CREDIT' ? '+' : '-'}{adjustPoints.toLocaleString()} PTS
                  </span>
                </div>
                <div className="flex justify-between text-white font-extrabold pt-1 border-t border-[#242424]">
                  <span>Resulting Balance:</span>
                  <span className="text-[#FF5500]">
                    {(
                      adjustType === 'CREDIT'
                        ? selectedMember.available_points + adjustPoints
                        : Math.max(0, selectedMember.available_points - adjustPoints)
                    ).toLocaleString()}{' '}
                    PTS
                  </span>
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-[#242424]">
                <button
                  type="button"
                  onClick={() => setAdjustModalOpen(false)}
                  className="px-4 py-2 text-xs font-bold text-[#9CA3AF] hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-5 py-2.5 bg-[#FF5500] hover:bg-[#E84F00] text-white text-xs font-extrabold rounded-xl shadow-md transition-all cursor-pointer disabled:opacity-50"
                >
                  {actionLoading ? 'Applying...' : 'Confirm Adjustment'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* MODAL: CAMPAIGN CREATE / EDIT */}
      {/* ============================================================ */}
      {campaignModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
          <div className="bg-[#121212] border border-[#2E2E2E] rounded-2xl max-w-lg w-full p-6 space-y-5 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-[#242424]">
              <h3 className="text-base font-extrabold text-white">
                {editingCampaign ? 'Edit Loyalty Campaign' : 'Create New Campaign'}
              </h3>
              <button
                onClick={() => setCampaignModalOpen(false)}
                className="text-[#9CA3AF] hover:text-white p-1"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSaveCampaign} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-white mb-1">
                  Campaign Name <span className="text-[#FF5500]">*</span>
                </label>
                <input
                  type="text"
                  placeholder="e.g. Weekend Double Points Special"
                  value={campName}
                  onChange={(e) => setCampName(e.target.value)}
                  className="w-full h-11 bg-[#1A1A1A] border border-[#2E2E2E] focus:border-[#FF5500] rounded-xl px-3.5 text-xs text-white focus:outline-none"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-white mb-1">
                    Campaign Type
                  </label>
                  <select
                    value={campType}
                    onChange={(e) => {
                      const val = e.target.value;
                      setCampType(val);
                      if (val === 'DOUBLE_POINTS') setCampMultiplier(2.0);
                      else if (val === 'TRIPLE_POINTS') setCampMultiplier(3.0);
                    }}
                    className="w-full h-11 bg-[#1A1A1A] border border-[#2E2E2E] focus:border-[#FF5500] rounded-xl px-3 text-xs text-white focus:outline-none cursor-pointer"
                  >
                    <option value="DOUBLE_POINTS">DOUBLE_POINTS (2x)</option>
                    <option value="TRIPLE_POINTS">TRIPLE_POINTS (3x)</option>
                    <option value="BONUS_POINTS">BONUS_POINTS (+PTS)</option>
                    <option value="CUSTOM_MULTIPLIER">CUSTOM_MULTIPLIER</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-white mb-1">
                    Points Multiplier
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    min="1.0"
                    max="10.0"
                    value={campMultiplier}
                    onChange={(e) => setCampMultiplier(Number(e.target.value))}
                    className="w-full h-11 bg-[#1A1A1A] border border-[#2E2E2E] focus:border-[#FF5500] rounded-xl px-3.5 text-xs text-white focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-white mb-1">
                  Bonus Fixed Points (Optional)
                </label>
                <input
                  type="number"
                  min="0"
                  step="50"
                  value={campBonus}
                  onChange={(e) => setCampBonus(Number(e.target.value))}
                  className="w-full h-11 bg-[#1A1A1A] border border-[#2E2E2E] focus:border-[#FF5500] rounded-xl px-3.5 text-xs text-white focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-white mb-1">Start Date</label>
                  <input
                    type="date"
                    value={campStartDate}
                    onChange={(e) => setCampStartDate(e.target.value)}
                    className="w-full h-11 bg-[#1A1A1A] border border-[#2E2E2E] focus:border-[#FF5500] rounded-xl px-3 text-xs text-white focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-white mb-1">End Date</label>
                  <input
                    type="date"
                    value={campEndDate}
                    onChange={(e) => setCampEndDate(e.target.value)}
                    className="w-full h-11 bg-[#1A1A1A] border border-[#2E2E2E] focus:border-[#FF5500] rounded-xl px-3 text-xs text-white focus:outline-none"
                  />
                </div>
              </div>

              <div className="flex items-center gap-3 pt-2">
                <input
                  type="checkbox"
                  id="campActive"
                  checked={campIsActive}
                  onChange={(e) => setCampIsActive(e.target.checked)}
                  className="w-4 h-4 accent-[#FF5500] rounded cursor-pointer"
                />
                <label htmlFor="campActive" className="text-xs font-bold text-white cursor-pointer">
                  Activate campaign immediately
                </label>
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-[#242424]">
                <button
                  type="button"
                  onClick={() => setCampaignModalOpen(false)}
                  className="px-4 py-2 text-xs font-bold text-[#9CA3AF] hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-5 py-2.5 bg-[#FF5500] hover:bg-[#E84F00] text-white text-xs font-extrabold rounded-xl shadow-md transition-all cursor-pointer disabled:opacity-50"
                >
                  {actionLoading ? 'Saving...' : 'Save Campaign'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
