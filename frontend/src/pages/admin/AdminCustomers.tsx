import React, { useState, useEffect } from 'react';
import { Search, Download, Loader2, RefreshCw, AlertCircle, Users } from 'lucide-react';
import { api } from '../../api/client';

export interface AdminCustomer {
  id: string;
  name: string;
  email: string;
  phone?: string | null;
  orders: number;
  points: number;
  lifetime_points?: number;
  is_active: boolean;
  created_at?: string | null;
}

export const AdminCustomers: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [customers, setCustomers] = useState<AdminCustomer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCustomers = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<AdminCustomer[]>('/customers');
      setCustomers(Array.isArray(data) ? data : []);
    } catch (err: any) {
      console.error('Failed to load customers:', err);
      setError(err?.message || 'Failed to load customers from database.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCustomers();
  }, []);

  const filteredCustomers = customers.filter(
    (c) =>
      c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (c.phone && c.phone.includes(searchQuery))
  );

  const handleExport = () => {
    if (customers.length === 0) return;
    const headers = ['Customer ID', 'Name', 'Email', 'Phone', 'Total Orders', 'Loyalty Points', 'Status', 'Joined Date'];
    const rows = customers.map((c) => [
      `"${c.id}"`,
      `"${c.name.replace(/"/g, '""')}"`,
      `"${c.email.replace(/"/g, '""')}"`,
      `"${(c.phone || '').replace(/"/g, '""')}"`,
      c.orders,
      c.points,
      c.is_active ? 'Active' : 'Inactive',
      c.created_at ? new Date(c.created_at).toLocaleDateString() : '',
    ]);

    const csvContent =
      'data:text/csv;charset=utf-8,' +
      [headers.join(','), ...rows.map((e) => e.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `patty_customers_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const getInitials = (name: string) => {
    if (!name) return 'C';
    const parts = name.trim().split(/\s+/);
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  };

  return (
    <div className="p-4 sm:p-6 lg:p-8 w-full max-w-[1680px] mx-auto space-y-6 text-[#F5F5F5]">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-[#F5F5F5] tracking-tight">Customers</h1>
          <p className="text-sm text-[#A1A1AA] font-normal mt-1">
            Authoritative customer records and loyalty point balances
          </p>
        </div>
        <button
          onClick={fetchCustomers}
          disabled={loading}
          className="h-10 px-3.5 bg-[#151515] border border-[#242424] hover:border-[#333333] text-[#A1A1AA] hover:text-[#F5F5F5] rounded-lg text-xs font-semibold flex items-center gap-2 transition-colors cursor-pointer disabled:opacity-50"
          title="Refresh customers list"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Customer Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-[#0D0D0D] border border-[#242424] p-3 rounded-lg">
        <div className="relative w-64 sm:w-80">
          <Search className="w-4 h-4 absolute left-3 top-3 text-[#71717A]" />
          <input
            type="text"
            placeholder="Search customers..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full h-10 bg-[#151515] border border-[#242424] focus:border-[#FF5A00] rounded-lg py-2 pl-9 pr-3.5 text-xs text-[#F5F5F5] placeholder-[#71717A] focus:outline-none transition-colors"
          />
        </div>

        <button
          onClick={handleExport}
          disabled={customers.length === 0}
          className="h-10 px-4 bg-[#151515] border border-[#242424] hover:border-[#333333] text-[#A1A1AA] hover:text-[#F5F5F5] rounded-lg text-xs font-semibold flex items-center gap-2 transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <Download className="w-3.5 h-3.5" />
          <span>Export ({customers.length})</span>
        </button>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="p-4 bg-red-950/40 border border-red-800/60 rounded-xl flex items-center justify-between text-red-300 text-xs">
          <div className="flex items-center gap-2.5">
            <AlertCircle className="w-4 h-4 shrink-0 text-red-400" />
            <span>{error}</span>
          </div>
          <button
            onClick={fetchCustomers}
            className="px-3 py-1 bg-red-900/60 hover:bg-red-800 border border-red-700 rounded text-white text-xs font-semibold transition-colors cursor-pointer"
          >
            Retry
          </button>
        </div>
      )}

      {/* Customers Data Table */}
      <div className="bg-[#0D0D0D] border border-[#242424] rounded-xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead className="bg-[#171717] text-[#A1A1AA] uppercase text-[11px] font-semibold border-b border-[#1C1C1C]">
              <tr>
                <th className="px-5 py-3.5">Customer</th>
                <th className="px-5 py-3.5">Contact</th>
                <th className="px-5 py-3.5 text-center">Total Orders</th>
                <th className="px-5 py-3.5 text-right">Loyalty Points</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1C1C1C] bg-[#0D0D0D]">
              {loading ? (
                <tr>
                  <td colSpan={4} className="px-5 py-16 text-center text-[#71717A]">
                    <div className="flex flex-col items-center justify-center gap-2.5">
                      <Loader2 className="w-6 h-6 animate-spin text-[#FF5A00]" />
                      <span className="text-xs">Loading real customer database records...</span>
                    </div>
                  </td>
                </tr>
              ) : filteredCustomers.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-5 py-16 text-center text-[#71717A]">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Users className="w-8 h-8 text-[#444444]" />
                      <p className="text-sm font-medium text-[#A1A1AA]">
                        {searchQuery ? 'No customers found matching your search.' : 'No registered customers found.'}
                      </p>
                      {searchQuery && (
                        <p className="text-xs text-[#71717A]">Try clearing your search query.</p>
                      )}
                    </div>
                  </td>
                </tr>
              ) : (
                filteredCustomers.map((c) => (
                  <tr key={c.id} className="hover:bg-[#121212] transition-colors h-14">
                    <td className="px-5 py-3 flex items-center gap-3">
                      <span className="w-9 h-9 rounded-full bg-[#241209] border border-[#6B2A0D] text-[#FF5A00] font-semibold text-xs flex items-center justify-center shrink-0">
                        {getInitials(c.name)}
                      </span>
                      <div className="min-w-0">
                        <p className="font-semibold text-[#F5F5F5] text-xs truncate">{c.name}</p>
                        <p className="text-[11px] text-[#71717A] truncate">{c.email}</p>
                      </div>
                    </td>
                    <td className="px-5 py-3 text-[#A1A1AA] font-normal">
                      {c.phone ? c.phone : <span className="text-[#555555] italic">No phone</span>}
                    </td>
                    <td className="px-5 py-3 text-center font-semibold text-[#F5F5F5]">{c.orders}</td>
                    <td className="px-5 py-3 text-right font-semibold text-[#FF5A00]">
                      {c.points.toLocaleString()}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
