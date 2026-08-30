import React, { useState, useEffect } from 'react';
import { X, Plus, Trash2, CheckCircle2, AlertCircle, ArrowUp, ArrowDown, MoveVertical, Loader2, Clock, Save } from 'lucide-react';
import { Category } from '../../types';
import { api } from '../../api/client';

interface Props {
  categories: Category[];
  onClose: () => void;
  onRefresh: () => void | Promise<void>;
}

export const AdminCategoryModal: React.FC<Props> = ({ categories, onClose, onRefresh }) => {
  const [categoryList, setCategoryList] = useState<Category[]>(categories);
  const [newCategoryName, setNewCategoryName] = useState('');
  const [loading, setLoading] = useState(false);
  const [reordering, setReordering] = useState(false);
  const [savingScheduleId, setSavingScheduleId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Local state for schedule inputs per category
  const [schedules, setSchedules] = useState<Record<string, { enabled: boolean; start: string; end: string }>>({});

  // Prevent body scrolling while modal is open
  useEffect(() => {
    const orig = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = orig;
    };
  }, []);

  // Sync categoryList when parent categories prop changes (excluding combo categories)
  useEffect(() => {
    const filtered = [...categories]
      .filter((c) => !c.slug?.toLowerCase().includes('combo') && !c.name?.toLowerCase().includes('combo'))
      .sort((a, b) => (a.display_order ?? 0) - (b.display_order ?? 0));
    setCategoryList(filtered);

    // Populate schedules map
    const schedMap: Record<string, { enabled: boolean; start: string; end: string }> = {};
    filtered.forEach((cat) => {
      schedMap[cat.id] = {
        enabled: Boolean(cat.schedule_enabled),
        start: cat.schedule_start_time || '08:00',
        end: cat.schedule_end_time || '12:00'
      };
    });
    setSchedules(schedMap);
  }, [categories]);

  const showFeedback = (msg: string, isError = false) => {
    if (isError) {
      setError(msg);
      setSuccess(null);
    } else {
      setSuccess(msg);
      setError(null);
    }
    setTimeout(() => {
      setError(null);
      setSuccess(null);
    }, 4000);
  };

  const handleCreateCategory = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = newCategoryName.trim();
    if (!trimmed) {
      showFeedback('Please enter a category name.', true);
      return;
    }

    if (categoryList.some((c) => c.name.trim().toLowerCase() === trimmed.toLowerCase())) {
      showFeedback(`Category "${trimmed}" already exists.`, true);
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(null);
    try {
      const created = await api.post<Category>('/categories', { 
        name: trimmed,
        display_order: categoryList.length,
        schedule_enabled: false
      });
      if (created) {
        setCategoryList((prev) => {
          const exists = prev.some((c) => c.id === created.id);
          if (exists) {
            return prev.map((c) => (c.id === created.id ? created : c));
          }
          return [...prev, created];
        });
        setSchedules((prev) => ({
          ...prev,
          [created.id]: {
            enabled: Boolean(created.schedule_enabled),
            start: created.schedule_start_time || '08:00',
            end: created.schedule_end_time || '12:00'
          }
        }));
      }
      setNewCategoryName('');
      showFeedback(`Category "${created?.name || trimmed}" created successfully!`);
      await onRefresh();
    } catch (err: any) {
      console.error(err);
      showFeedback(err?.message || err?.detail || 'Failed to create category.', true);
    } finally {
      setLoading(false);
    }
  };

  const handleMovePosition = async (index: number, direction: 'up' | 'down') => {
    if (reordering) return;
    const targetIndex = direction === 'up' ? index - 1 : index + 1;
    if (targetIndex < 0 || targetIndex >= categoryList.length) return;

    const updatedList = [...categoryList];
    const [movedItem] = updatedList.splice(index, 1);
    updatedList.splice(targetIndex, 0, movedItem);

    // Re-assign display_order indices sequentially
    const payloadOrders = updatedList.map((cat, idx) => ({
      id: cat.id,
      display_order: idx
    }));

    // Optimistic UI update
    setCategoryList(updatedList.map((cat, idx) => ({ ...cat, display_order: idx })));
    setReordering(true);

    try {
      const serverUpdated = await api.put<Category[]>('/categories/reorder', { orders: payloadOrders });
      if (serverUpdated && Array.isArray(serverUpdated)) {
        setCategoryList(serverUpdated);
      }
      showFeedback(`Position updated: "${movedItem.name}" is now #${targetIndex + 1}`);
      onRefresh();
    } catch (err: any) {
      console.error(err);
      showFeedback(err?.message || 'Failed to update category order.', true);
      setCategoryList(categories);
    } finally {
      setReordering(false);
    }
  };

  const handleDeleteCategory = async (id: string, name: string) => {
    if (window.confirm(`Are you sure you want to delete the category "${name}"?`)) {
      setError(null);
      setSuccess(null);
      try {
        await api.delete(`/categories/${id}`);
        setCategoryList((prev) => prev.filter((c) => c.id !== id));
        showFeedback(`Category "${name}" removed.`);
        onRefresh();
      } catch (err: any) {
        console.error(err);
        showFeedback(err?.message || err?.detail || 'Failed to delete category.', true);
      }
    }
  };

  const handleSaveSchedule = async (cat: Category) => {
    const current = schedules[cat.id] || {
      enabled: Boolean(cat.schedule_enabled),
      start: cat.schedule_start_time || '08:00',
      end: cat.schedule_end_time || '12:00'
    };

    if (current.enabled && current.start === current.end) {
      showFeedback('Start time and end time cannot be equal.', true);
      return;
    }

    setSavingScheduleId(cat.id);
    setError(null);
    setSuccess(null);
    try {
      const updated = await api.put<Category>(`/categories/${cat.id}/schedule`, {
        schedule_enabled: current.enabled,
        schedule_start_time: current.start,
        schedule_end_time: current.end
      });

      if (updated) {
        setCategoryList((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
      }
      showFeedback(`Schedule for "${cat.name}" updated successfully!`);
      await onRefresh();
    } catch (err: any) {
      console.error(err);
      showFeedback(err?.response?.data?.detail || err?.message || 'Failed to update category schedule.', true);
    } finally {
      setSavingScheduleId(null);
    }
  };

  return (
    <div className="admin-modal-overlay">
      <div className="admin-modal-container bg-[#121212] border border-[#262626] rounded-2xl max-w-xl shadow-2xl p-4 sm:p-6 relative flex flex-col text-white max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 sm:pb-4 border-b border-[#262626] mb-4 sm:mb-5 shrink-0">
          <div>
            <h2 className="text-base sm:text-lg font-bold text-white tracking-wide">Manage Categories & Schedules</h2>
            <p className="text-xs text-[#9CA3AF]">Create, reorder positions, and configure daily serving hours</p>
          </div>
          <button 
            onClick={onClose} 
            className="p-1.5 text-[#9CA3AF] hover:text-white rounded-xl hover:bg-[#1A1A1A] cursor-pointer shrink-0"
            aria-label="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Feedback Toasts */}
        {error && (
          <div className="mb-4 p-3 bg-[#2A1215] border border-[#EF4444]/40 text-[#FCA5A5] rounded-xl text-xs font-semibold flex items-center gap-2 shrink-0">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}
        {success && (
          <div className="mb-4 p-3 bg-[#132A1B] border border-[#22C55E]/40 text-[#86EFAC] rounded-xl text-xs font-semibold flex items-center gap-2 shrink-0">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{success}</span>
          </div>
        )}

        {/* Create Category Form */}
        <form onSubmit={handleCreateCategory} className="mb-4 space-y-2 shrink-0">
          <label className="block text-xs font-semibold text-[#D1D5DB]">Add New Category</label>
          <div className="flex gap-2">
            <input
              type="text"
              autoFocus
              value={newCategoryName}
              onChange={(e) => setNewCategoryName(e.target.value)}
              placeholder="e.g. Breakfast, Burgers, Tenders, Desserts"
              className="flex-1 bg-[#1A1A1A] border border-[#262626] rounded-xl py-2 px-3 text-xs text-white placeholder-[#6B7280] focus:outline-none focus:border-[#FF5500]"
              required
            />
            <button
              type="submit"
              disabled={loading}
              className="bg-[#FF5500] hover:bg-[#E04B00] text-white px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-1.5 transition-all disabled:opacity-50 cursor-pointer shadow-md shadow-[#FF5500]/20"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
              <span>{loading ? 'Adding...' : 'Add'}</span>
            </button>
          </div>
        </form>

        {/* Existing Categories List with Position & Schedule Controls */}
        <div className="flex-1 min-h-0 flex flex-col space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold text-[#9CA3AF] uppercase">
              Categories & Daily Schedules ({categoryList.length})
            </h3>
            <span className="text-[10px] text-[#6B7280] flex items-center gap-1">
              <MoveVertical className="w-3 h-3" />
              Use ▲ / ▼ to reorder
            </span>
          </div>

          <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
            {categoryList.length === 0 ? (
              <p className="text-xs text-[#9CA3AF] py-6 text-center">No categories found.</p>
            ) : (
              categoryList.map((c, index) => {
                const isFirst = index === 0;
                const isLast = index === categoryList.length - 1;
                const sched = schedules[c.id] || {
                  enabled: Boolean(c.schedule_enabled),
                  start: c.schedule_start_time || '08:00',
                  end: c.schedule_end_time || '12:00'
                };
                const isSaving = savingScheduleId === c.id;

                return (
                  <div
                    key={c.id}
                    className="bg-[#1A1A1A] border border-[#262626] p-3 rounded-xl hover:border-[#333333] transition-colors space-y-2.5"
                  >
                    {/* Top Row: Position, Name, Reorder, Delete */}
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2.5 min-w-0 flex-1">
                        <span className="w-6 h-6 rounded-lg bg-black border border-[#2E2E2E] flex items-center justify-center text-[10px] font-black text-[#FF5500] font-mono shrink-0">
                          {index + 1}
                        </span>
                        <div className="min-w-0 flex-1">
                          <span className="text-xs font-bold text-white block truncate">{c.name}</span>
                          <span className="text-[10px] text-[#6B7280] font-mono truncate block">/{c.slug}</span>
                        </div>
                      </div>

                      {/* Position Reorder & Delete Buttons */}
                      <div className="flex items-center gap-1 shrink-0">
                        <button
                          type="button"
                          onClick={() => handleMovePosition(index, 'up')}
                          disabled={isFirst || reordering}
                          className={`p-1.5 rounded-lg border transition-colors cursor-pointer ${
                            isFirst
                              ? 'opacity-25 border-transparent text-[#666] cursor-not-allowed'
                              : 'border-[#2A2A2A] bg-[#141414] hover:bg-[#222] hover:border-[#FF5500]/50 text-[#D1D5DB] hover:text-[#FF5500]'
                          }`}
                          title="Move Up"
                        >
                          <ArrowUp className="w-3.5 h-3.5" />
                        </button>

                        <button
                          type="button"
                          onClick={() => handleMovePosition(index, 'down')}
                          disabled={isLast || reordering}
                          className={`p-1.5 rounded-lg border transition-colors cursor-pointer ${
                            isLast
                              ? 'opacity-25 border-transparent text-[#666] cursor-not-allowed'
                              : 'border-[#2A2A2A] bg-[#141414] hover:bg-[#222] hover:border-[#FF5500]/50 text-[#D1D5DB] hover:text-[#FF5500]'
                          }`}
                          title="Move Down"
                        >
                          <ArrowDown className="w-3.5 h-3.5" />
                        </button>

                        <button
                          type="button"
                          onClick={() => handleDeleteCategory(c.id, c.name)}
                          className="p-1.5 text-[#9CA3AF] hover:text-[#EF4444] hover:bg-[#2A1215] rounded-lg transition-colors cursor-pointer ml-1"
                          title="Delete Category"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>

                    {/* Schedule Controls Row */}
                    <div className="bg-[#111111] border border-[#242424] rounded-lg p-2.5 flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <Clock className="w-3.5 h-3.5 text-[#FF5500] shrink-0" />
                        <span className="text-[11px] font-semibold text-[#D1D5DB]">Daily Schedule:</span>
                        <button
                          type="button"
                          onClick={() =>
                            setSchedules((prev) => ({
                              ...prev,
                              [c.id]: { ...sched, enabled: !sched.enabled }
                            }))
                          }
                          className={`px-2 py-0.5 rounded text-[10px] font-extrabold cursor-pointer border transition-colors ${
                            sched.enabled
                              ? 'bg-[#FF5500]/20 text-[#FF5500] border-[#FF5500]/50 hover:bg-[#FF5500]/30'
                              : 'bg-[#222] text-[#888] border-[#333] hover:bg-[#2a2a2a]'
                          }`}
                        >
                          {sched.enabled ? 'ON' : 'OFF'}
                        </button>
                      </div>

                      {/* Time Inputs (When Schedule Enabled) */}
                      {sched.enabled ? (
                        <div className="flex items-center gap-1.5">
                          <span className="text-[10px] text-[#888]">From</span>
                          <input
                            type="time"
                            value={sched.start}
                            onChange={(e) =>
                              setSchedules((prev) => ({
                                ...prev,
                                [c.id]: { ...sched, start: e.target.value }
                              }))
                            }
                            className="bg-[#1A1A1A] border border-[#333] rounded px-1.5 py-0.5 text-xs text-white focus:outline-none focus:border-[#FF5500]"
                          />
                          <span className="text-[10px] text-[#888]">To</span>
                          <input
                            type="time"
                            value={sched.end}
                            onChange={(e) =>
                              setSchedules((prev) => ({
                                ...prev,
                                [c.id]: { ...sched, end: e.target.value }
                              }))
                            }
                            className="bg-[#1A1A1A] border border-[#333] rounded px-1.5 py-0.5 text-xs text-white focus:outline-none focus:border-[#FF5500]"
                          />
                        </div>
                      ) : null}

                      {/* Current Status Badge & Save Button */}
                      <div className="flex items-center gap-2 ml-auto">
                        <span
                          className={`text-[9px] font-bold px-1.5 py-0.5 rounded border uppercase tracking-wider ${
                            !sched.enabled
                              ? 'bg-[#1F1F1F] text-[#888] border-[#2E2E2E]'
                              : c.schedule_status === 'OPEN'
                              ? 'bg-emerald-950/70 text-emerald-400 border-emerald-500/50'
                              : 'bg-rose-950/70 text-rose-400 border-rose-500/50'
                          }`}
                        >
                          {!sched.enabled
                            ? 'Normal availability'
                            : c.schedule_status === 'OPEN'
                            ? 'OPEN'
                            : 'CLOSED'}
                        </span>

                        <button
                          type="button"
                          disabled={isSaving}
                          onClick={() => handleSaveSchedule(c)}
                          className="bg-[#242424] hover:bg-[#FF5500] text-white border border-[#333] hover:border-[#FF5500] px-2.5 py-1 rounded text-[10px] font-bold flex items-center gap-1 transition-all cursor-pointer disabled:opacity-50"
                          title="Save Schedule"
                        >
                          {isSaving ? (
                            <Loader2 className="w-3 h-3 animate-spin" />
                          ) : (
                            <Save className="w-3 h-3" />
                          )}
                          <span>Save</span>
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="pt-3 mt-3 border-t border-[#262626] flex justify-end shrink-0">
          <button
            type="button"
            onClick={onClose}
            className="px-5 py-2 bg-[#1A1A1A] hover:bg-[#262626] text-white rounded-xl text-xs font-semibold cursor-pointer border border-[#2E2E2E]"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
