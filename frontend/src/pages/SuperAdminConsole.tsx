import React, { useState, useEffect, useCallback } from 'react';
import { hackathonsApi } from '@/api/client';
import {
  Shield,
  Plus,
  Trash2,
  Lock,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  Loader2,
  Calendar,
  Users,
  Settings,
} from 'lucide-react';

interface HackathonItem {
  id: number;
  name: string;
  template_id: string | null;
  admin_id: string | null;
  team_count: number;
  created_at: string | null;
}

export default function SuperAdminConsole() {
  const [hackathons, setHackathons] = useState<HackathonItem[]>([]);
  const [templates, setTemplates] = useState<Record<string, { name: string; description: string }>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Form States for creating a project
  const [name, setName] = useState('');
  const [adminId, setAdminId] = useState('');
  const [adminPass, setAdminPass] = useState('');
  const [selectedTemplate, setSelectedTemplate] = useState('');

  // Passcode reset state
  const [resettingId, setResettingId] = useState<number | null>(null);
  const [newPass, setNewPass] = useState('');

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const list = await hackathonsApi.list();
      setHackathons(list);

      const tpls = await hackathonsApi.getTemplates();
      setTemplates(tpls);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const showSuccess = (msg: string) => {
    setSuccess(msg);
    setTimeout(() => setSuccess(''), 4000);
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !adminId || !adminPass) return;

    try {
      setError('');
      setLoading(true);
      await hackathonsApi.create({
        name,
        admin_id: adminId,
        admin_pass: adminPass,
        template_id: selectedTemplate || undefined,
      });
      setName('');
      setAdminId('');
      setAdminPass('');
      setSelectedTemplate('');
      showSuccess(`Hackathon "${name}" created successfully!`);
      loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to create project.');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number, projectName: string) => {
    if (!window.confirm(`WARNING: Are you sure you want to delete "${projectName}"? This will delete all users, submissions, configurations, and evaluations associated with this project. This action cannot be undone.`)) {
      return;
    }

    try {
      setError('');
      await hackathonsApi.delete(id);
      showSuccess(`Project "${projectName}" has been permanently deleted.`);
      loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to delete project.');
    }
  };

  const handleResetPasscode = async (id: number) => {
    if (!newPass.trim()) return;

    try {
      setError('');
      await hackathonsApi.resetAdminPasscode(id, newPass);
      showSuccess(`Admin passcode for project ID ${id} reset successfully.`);
      setResettingId(null);
      setNewPass('');
    } catch (err: any) {
      setError(err.message || 'Failed to reset passcode.');
    }
  };

  return (
    <div className="superadmin-page">
      <div className="page-header">
        <Shield size={32} />
        <div>
          <h1>Super Admin Console</h1>
          <p className="page-subtitle">Manage project databases, tenants and admin credentials.</p>
        </div>
      </div>

      {error && (
        <div className="alert alert-error">
          <AlertTriangle size={18} />
          <span>{error}</span>
        </div>
      )}

      {success && (
        <div className="alert alert-success">
          <CheckCircle size={18} />
          <span>{success}</span>
        </div>
      )}

      <div className="superadmin-grid">
        {/* Creation Card */}
        <div className="card">
          <h4>Create New Project (Tenant)</h4>
          <form onSubmit={handleCreate} className="vertical-form mt-4">
            <div className="form-group">
              <label>Hackathon Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. AI Innovation Summit 2026"
                required
              />
            </div>
            <div className="form-group">
              <label>Host Admin ID</label>
              <input
                type="text"
                value={adminId}
                onChange={(e) => setAdminId(e.target.value)}
                placeholder="e.g. admin-innovate"
                required
              />
            </div>
            <div className="form-group">
              <label>Host Admin Passcode</label>
              <input
                type="password"
                value={adminPass}
                onChange={(e) => setAdminPass(e.target.value)}
                placeholder="Secure initial passcode"
                required
              />
            </div>
            <div className="form-group">
              <label>Jury Evaluation Template (Optional)</label>
              <select
                value={selectedTemplate}
                onChange={(e) => setSelectedTemplate(e.target.value)}
              >
                <option value="">— Generic Template —</option>
                {Object.entries(templates).map(([key, tpl]) => (
                  <option key={key} value={key}>
                    {tpl.name}
                  </option>
                ))}
              </select>
              {selectedTemplate && templates[selectedTemplate] && (
                <p className="template-desc dim-text text-xs mt-1">
                  {templates[selectedTemplate].description}
                </p>
              )}
            </div>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
              Create Project
            </button>
          </form>
        </div>

        {/* Project Lists */}
        <div className="card project-list-card">
          <div className="card-header-flex">
            <h4>Existing Projects ({hackathons.length})</h4>
            <button onClick={loadData} className="btn btn-ghost btn-sm" disabled={loading}>
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
            </button>
          </div>

          <div className="project-items mt-4">
            {hackathons.map((h) => (
              <div key={h.id} className="project-item-row">
                <div className="project-info">
                  <h5>{h.name}</h5>
                  <div className="project-meta-pills">
                    <span className="pill">
                      <Calendar size={12} />
                      ID: {h.id}
                    </span>
                    <span className="pill">
                      <Users size={12} />
                      {h.team_count} Teams
                    </span>
                    {h.template_id && (
                      <span className="pill">
                        <Settings size={12} />
                        Template: {h.template_id}
                      </span>
                    )}
                    <span className="pill admin-pill">Admin: {h.admin_id}</span>
                  </div>
                </div>

                <div className="project-actions">
                  {resettingId === h.id ? (
                    <div className="reset-passcode-inline">
                      <input
                        type="password"
                        placeholder="New passcode"
                        value={newPass}
                        onChange={(e) => setNewPass(e.target.value)}
                      />
                      <button onClick={() => handleResetPasscode(h.id)} className="btn btn-success btn-xs">
                        Save
                      </button>
                      <button onClick={() => setResettingId(null)} className="btn btn-ghost btn-xs">
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button onClick={() => setResettingId(h.id)} className="btn btn-secondary btn-sm">
                      <Lock size={14} /> Reset Passcode
                    </button>
                  )}

                  <button
                    onClick={() => handleDelete(h.id, h.name)}
                    className="btn btn-danger btn-sm"
                  >
                    <Trash2 size={14} /> Delete
                  </button>
                </div>
              </div>
            ))}

            {hackathons.length === 0 && !loading && (
              <p className="dim-text text-center py-6">No projects created yet. Use the form on the left.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
