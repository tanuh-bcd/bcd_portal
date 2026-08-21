import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-toastify';
import Layout from '../Layout';

const tabContainerStyle = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  backgroundColor: 'white',
  borderBottom: '1px solid #ddd',
  padding: '0 20px',
  borderRadius: '8px 8px 0 0'
};

const tabButtonStyle = {
  padding: '15px 30px',
  fontSize: '16px',
  background: 'none',
  border: 'none',
  borderBottom: '3px solid #14868C',
  color: '#14868C',
  fontWeight: 'bold'
};

const cardStyle = {
  border: '1px solid #B7E0D8',
  borderRadius: '8px',
  backgroundColor: '#F3FAF8',
  marginBottom: '30px'
};

const cardHeaderStyle = {
  padding: '18px 20px',
  fontWeight: 'bold',
  fontSize: '17px',
  color: '#1a1a1a',
  borderRadius: '8px 8px 0 0'
};

const fieldWrapStyle = { padding: '0 20px 20px' };

const fieldGroupStyle = { marginBottom: '16px', position: 'relative' };

const labelStyle = {
  display: 'block',
  marginBottom: '6px',
  fontWeight: 500,
  fontSize: '14px',
  color: '#333'
};

const buttonStyle = {
  padding: '10px 20px',
  backgroundColor: '#14868C',
  color: 'white',
  border: 'none',
  borderRadius: '4px',
  cursor: 'pointer',
  fontWeight: 'bold'
};

const modalOverlayStyle = {
  position: 'fixed',
  inset: 0,
  backgroundColor: 'rgba(0,0,0,0.4)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 1000
};

const modalStyle = {
  backgroundColor: 'white',
  padding: '24px',
  borderRadius: '8px',
  minWidth: '280px',
  textAlign: 'center'
};

const modalActionsStyle = {
  display: 'flex',
  gap: '12px',
  justifyContent: 'center',
  marginTop: '16px'
};

const modalYesStyle = {
  padding: '8px 20px',
  borderRadius: '6px',
  border: 'none',
  cursor: 'pointer',
  backgroundColor: '#14868C',
  color: 'white'
};

const modalNoStyle = {
  padding: '8px 20px',
  borderRadius: '6px',
  border: 'none',
  cursor: 'pointer',
  backgroundColor: '#eee',
  color: '#333'
};

// --- Searchable dropdown styles ---
const ddTriggerStyle = {
  width: '100%',
  padding: '10px 12px',
  borderRadius: '6px',
  border: '1px solid #cfd8dc',
  backgroundColor: 'white',
  fontSize: '14px',
  boxSizing: 'border-box',
  textAlign: 'left',
  cursor: 'pointer',
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  gap: '8px'
};

const ddTriggerTextStyle = {
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
  color: '#333'
};

const ddPanelStyle = {
  position: 'absolute',
  top: 'calc(100% + 4px)',
  left: 0,
  right: 0,
  backgroundColor: 'white',
  border: '1px solid #cfd8dc',
  borderRadius: '6px',
  boxShadow: '0 4px 14px rgba(0,0,0,0.12)',
  zIndex: 20,
  overflow: 'hidden'
};

const ddSearchWrapStyle = {
  padding: '8px',
  borderBottom: '1px solid #eee'
};

const ddSearchInputStyle = {
  width: '100%',
  padding: '8px 10px',
  borderRadius: '4px',
  border: '1px solid #cfd8dc',
  fontSize: '13px',
  boxSizing: 'border-box'
};

const DROPDOWN_LIST_HEIGHT = 220;

const ddListStyle = {
  height: DROPDOWN_LIST_HEIGHT,
  overflowY: 'auto'
};

const ddOptionStyle = {
  padding: '9px 12px',
  fontSize: '14px',
  color: '#333',
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  gap: '10px'
};

const ddOptionHoverStyle = {
  backgroundColor: '#F3FAF8'
};

const ddEmptyStyle = {
  padding: '14px 12px',
  fontSize: '13px',
  color: '#888',
  textAlign: 'center'
};

/**
 * Generic searchable dropdown.
 * - multiple=false: single select, click an option to choose + close.
 * - multiple=true: checkbox per option, stays open, selected values via array.
 */
const SearchableDropdown = ({
  options,
  getValue,
  getLabel,
  multiple = false,
  selected,
  onChange,
  placeholder,
  loading,
  emptyText = 'No results found'
}) => {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [hoverIdx, setHoverIdx] = useState(-1);
  const containerRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const filtered = options.filter((opt) =>
    getLabel(opt).toLowerCase().includes(query.toLowerCase())
  );

  const isSelected = (opt) =>
    multiple
      ? selected.includes(getValue(opt))
      : selected === getValue(opt);

  const handleSelect = (opt) => {
    if (multiple) {
      const val = getValue(opt);
      const next = selected.includes(val)
        ? selected.filter((v) => v !== val)
        : [...selected, val];
      onChange(next);
    } else {
      onChange(getValue(opt));
      setOpen(false);
      setQuery('');
    }
  };

  const triggerLabel = () => {
    if (loading) return 'Loading...';
    if (multiple) {
      if (selected.length === 0) return placeholder;
      if (selected.length === 1) {
        const opt = options.find((o) => getValue(o) === selected[0]);
        return opt ? getLabel(opt) : `1 selected`;
      }
      return `${selected.length} selected`;
    }
    const opt = options.find((o) => getValue(o) === selected);
    return opt ? getLabel(opt) : placeholder;
  };

  return (
    <div ref={containerRef} style={{ position: 'relative' }}>
      <button
        type="button"
        style={ddTriggerStyle}
        onClick={() => !loading && setOpen((o) => !o)}
        disabled={loading}
      >
        <span style={ddTriggerTextStyle}>{triggerLabel()}</span>
        <span style={{ color: '#888', fontSize: '11px' }}>{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div style={ddPanelStyle}>
          <div style={ddSearchWrapStyle}>
            <input
              autoFocus
              type="text"
              placeholder="Search..."
              value={query}
              onChange={(e) => { setQuery(e.target.value); setHoverIdx(-1); }}
              style={ddSearchInputStyle}
            />
          </div>
          <div style={ddListStyle}>
            {filtered.length === 0 && <div style={ddEmptyStyle}>{emptyText}</div>}
            {filtered.map((opt, idx) => {
              const val = getValue(opt);
              const selectedFlag = isSelected(opt);
              return (
                <div
                  key={val}
                  style={{
                    ...ddOptionStyle,
                    ...(hoverIdx === idx ? ddOptionHoverStyle : {}),
                    ...(selectedFlag && !multiple ? { backgroundColor: '#E6F4F1' } : {})
                  }}
                  onMouseEnter={() => setHoverIdx(idx)}
                  onMouseLeave={() => setHoverIdx(-1)}
                  onClick={() => handleSelect(opt)}
                >
                  {multiple && (
                    <input
                      type="checkbox"
                      checked={selectedFlag}
                      readOnly
                      style={{ cursor: 'pointer' }}
                    />
                  )}
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {getLabel(opt)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

const QCAdminDashboard = () => {
  const navigate = useNavigate();

  // --- Auth guard ---
  const [qcRole, setQcRole] = useState('');
  const [qcUserName, setQcUserName] = useState('');
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    const role = localStorage.getItem('qcRole');
    const token = localStorage.getItem('qcToken');
    const userName = localStorage.getItem('qcUserName');

    if (!token || !role) {
      navigate('/qc-bcd-login');
      return;
    }

    setQcRole(role);
    setQcUserName(userName || '');
    setAuthChecked(true);
  }, [navigate]);

  const handleLogout = () => {
    localStorage.removeItem('qcToken');
    localStorage.removeItem('qcRole');
    localStorage.removeItem('qcUserEmail');
    localStorage.removeItem('qcUserName');
    navigate('/qc-bcd-login');
  };
  // -------------------

  const apiBase = process.env.REACT_APP_API_URL || '';
  const authHeaders = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('qcToken')}`
  };

  const [users, setUsers] = useState([]);
  const [usersLoading, setUsersLoading] = useState(true);

  const [subjects, setSubjects] = useState([]);
  const [subjectsLoading, setSubjectsLoading] = useState(true);

  const [selectedUser, setSelectedUser] = useState('');
  const [selectedSubjects, setSelectedSubjects] = useState([]); // now an array

  const [showConfirm, setShowConfirm] = useState(false);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!authChecked) return;
    fetchUsers();
    fetchSubjects();
    // eslint-disable-next-line
  }, [authChecked]);

  const fetchUsers = async () => {
    setUsersLoading(true);
    try {
      const response = await fetch(`${apiBase}/api/v1/qc/users`, { headers: authHeaders });
      if (response.status === 401) {
        toast.error('Session expired, please log in again');
        navigate('/qc-bcd-login');
        return;
      }
      if (!response.ok) throw new Error('Failed to fetch users');
      const data = await response.json();
      setUsers(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Failed to fetch users', err);
      toast.error('Failed to load users list');
    } finally {
      setUsersLoading(false);
    }
  };

  const fetchSubjects = async () => {
    setSubjectsLoading(true);
    try {
      const response = await fetch(`${apiBase}/api/v1/qc/subjects`, { headers: authHeaders });
      if (response.status === 401) {
        toast.error('Session expired, please log in again');
        navigate('/qc-bcd-login');
        return;
      }
      if (!response.ok) throw new Error('Failed to fetch subjects');
      const data = await response.json();
      setSubjects(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Failed to fetch subjects', err);
      toast.error('Failed to load subjects list');
    } finally {
      setSubjectsLoading(false);
    }
  };

  const handleCreateClick = () => {
    if (!selectedUser || selectedSubjects.length === 0) {
      toast.error('Please select a user and at least one subject');
      return;
    }
    setShowConfirm(true);
  };
const confirmCreate = async () => {
  setCreating(true);
  try {
    const response = await fetch(`${apiBase}/api/v1/qc/assignments`, {
      method: 'POST',
      headers: authHeaders,
      body: JSON.stringify({
        assessment_ids: selectedSubjects.map(Number),
        radiologist_id: Number(selectedUser),
        assigned: 'yes'
      })
    });
    const data = await response.json();
    if (response.ok) {
      const createdCount = data.created?.length || 0;
      const skippedCount = data.skipped?.length || 0;
      toast.success(
        `${createdCount} stud${createdCount === 1 ? 'y' : 'ies'} created` +
        (skippedCount ? `, ${skippedCount} already assigned` : '')
      );
      setSelectedUser('');
      setSelectedSubjects([]);
    } else {
      toast.error(data.detail || 'Failed to create study');
    }
  } catch (err) {
    console.error('Create study error', err);
    toast.error('An error occurred while creating the study');
  } finally {
    setCreating(false);
    setShowConfirm(false);
  }
};
  if (!authChecked) {
    return null;
  }

  const selectedSubjectLabels = subjects
    .filter((s) => selectedSubjects.includes(String(s.qc_id)))
    .map((s) => s.display_id);

  return (
    <Layout userRole={qcRole} handleLogout={handleLogout} fullWidth={true}>
      <div style={tabContainerStyle}>
        <button style={tabButtonStyle}>QC Admin</button>
        <span style={{ fontSize: '14px', color: '#666' }}>
          {qcUserName ? `Logged in as ${qcUserName}` : ''}
        </span>
      </div>

      <div style={{ marginTop: '20px' }}>
        <div style={cardStyle}>
          <div style={cardHeaderStyle}>Create New Study</div>
          <div style={fieldWrapStyle}>
            <div style={fieldGroupStyle}>
              <label style={labelStyle}>Assign User</label>
              <SearchableDropdown
                options={users}
                getValue={(u) => String(u.qc_id)}
                getLabel={(u) => u.qc_full_name || u.qc_email}
                multiple={false}
                selected={selectedUser}
                onChange={setSelectedUser}
                placeholder="Select User"
                loading={usersLoading}
                emptyText="No users found"
              />
            </div>

            <div style={fieldGroupStyle}>
              <label style={labelStyle}>Assign Subjects</label>
              <SearchableDropdown
                options={subjects}
                getValue={(s) => String(s.qc_id)}
                getLabel={(s) => s.display_id}
                multiple={true}
                selected={selectedSubjects}
                onChange={setSelectedSubjects}
                placeholder="Select Subjects"
                loading={subjectsLoading}
                emptyText="No subjects found"
              />
              {selectedSubjects.length > 0 && (
                <div style={{ marginTop: '8px', fontSize: '12.5px', color: '#555' }}>
                  {selectedSubjects.length} selected: {selectedSubjectLabels.join(', ')}
                </div>
              )}
            </div>

            <button
              style={{ ...buttonStyle, opacity: creating ? 0.7 : 1 }}
              onClick={handleCreateClick}
              disabled={creating}
            >
              Create New Study
            </button>
          </div>
        </div>
      </div>

      {showConfirm && (
        <div style={modalOverlayStyle}>
          <div style={modalStyle}>
            <p>
              Create {selectedSubjects.length} stud{selectedSubjects.length === 1 ? 'y' : 'ies'} with the selected user?
            </p>
            <div style={modalActionsStyle}>
              <button style={modalYesStyle} onClick={confirmCreate} disabled={creating}>
                {creating ? 'Creating...' : 'Yes'}
              </button>
              <button
                style={modalNoStyle}
                onClick={() => setShowConfirm(false)}
                disabled={creating}
              >
                No
              </button>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
};

export default QCAdminDashboard;