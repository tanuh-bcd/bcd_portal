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
  margin: '10px'
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

const qcThStyle = {
  padding: '10px 12px',
  textAlign: 'left',
  color: '#495057',
  fontWeight: '600',
  whiteSpace: 'nowrap',
  backgroundColor: '#fff',
  borderRight: '1px solid #dee2e6',
  borderBottom: '1px solid #dee2e6',
};

const qcTdStyle = {
  padding: '10px 12px',
  backgroundColor: '#fff',
  borderRight: '1px solid #dee2e6',
  borderBottom: '1px solid #dee2e6',
};

const RISK_COLORS = {
  'Baseline Risk': '#6ee7b7',
  'Evident Risk': '#fde047',
  'Significant Risk': '#fb923c',
  'High Risk': '#fb7185'
};

const statusCellStyle = (isTrue) => ({
  padding: '10px 12px',
  textAlign: 'left',
  color: isTrue ? 'green' : 'red',
  fontWeight: 'bold',
});

const SearchableDropdown = ({
  options,
  getValue,
  getLabel,
  getDisabled = () => false,
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
    if (getDisabled(opt)) return;   // NEW - block selection
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

  // in the option render:
  {
    filtered.map((opt, idx) => {
      const val = getValue(opt);
      const selectedFlag = isSelected(opt);
      const disabled = getDisabled(opt);   // NEW
      return (
        <div
          key={val}
          style={{
            ...ddOptionStyle,
            ...(hoverIdx === idx && !disabled ? ddOptionHoverStyle : {}),
            ...(selectedFlag && !multiple ? { backgroundColor: '#E6F4F1' } : {}),
            ...(disabled ? { opacity: 0.45, cursor: 'not-allowed', backgroundColor: '#f5f5f5' } : {})
          }}
          onMouseEnter={() => !disabled && setHoverIdx(idx)}
          onMouseLeave={() => setHoverIdx(-1)}
          onClick={() => handleSelect(opt)}
        >
          {multiple && (
            <input type="checkbox" checked={selectedFlag} readOnly disabled={disabled} style={{ cursor: disabled ? 'not-allowed' : 'pointer' }} />
          )}
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {getLabel(opt)}{disabled ? ' (Already Assigned)' : ''}
          </span>
        </div>
      );
    })
  }

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
              const disabled = getDisabled(opt);
              return (
                <div
                  key={val}
                  style={{
                    ...ddOptionStyle,
                    ...(hoverIdx === idx && !disabled ? ddOptionHoverStyle : {}),
                    ...(selectedFlag && !multiple ? { backgroundColor: '#E6F4F1' } : {}),
                    ...(disabled ? { opacity: 0.45, cursor: 'not-allowed', backgroundColor: '#f5f5f5' } : {})
                  }}
                  onMouseEnter={() => !disabled && setHoverIdx(idx)}
                  onMouseLeave={() => setHoverIdx(-1)}
                  onClick={() => handleSelect(opt)}
                >
                  {multiple && (
                    <input
                      type="checkbox"
                      checked={selectedFlag}
                      readOnly
                      disabled={disabled}
                      style={{ cursor: disabled ? 'not-allowed' : 'pointer' }}
                    />
                  )}
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {getLabel(opt)}{disabled ? ' (Already Assigned)' : ''}
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
  const [selectedSubjects, setSelectedSubjects] = useState([]);
  const [showConfirm, setShowConfirm] = useState(false);
  const [creating, setCreating] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [fullName, setFullName] = useState('');
  const [allAssignments, setAllAssignments] = useState([]);
  const [allAssignmentsLoading, setAllAssignmentsLoading] = useState(true);
  const [selectedAdminSubject, setSelectedAdminSubject] = useState(null);
  const [isAdminModalOpen, setIsAdminModalOpen] = useState(false);
  const [adminDetailLoading, setAdminDetailLoading] = useState(false);
  const [totalSubjects, setTotalSubjects] = useState(0);

  const fetchAdminSubjectDetail = async (sessionId, radiologistId) => {
    setAdminDetailLoading(true);
    try {
      const response = await fetch(
        `${apiBase}/api/v1/qc/radiologist/${radiologistId}/subjects/${sessionId}`,
        { headers: authHeaders }
      );
      if (response.status === 401) {
        toast.error('Session expired, please log in again');
        navigate('/qc-bcd-login');
        return;
      }
      if (!response.ok) throw new Error('Failed to fetch subject details');
      const data = await response.json();
      setSelectedAdminSubject(data);
      setIsAdminModalOpen(true);
    } catch (err) {
      console.error('Failed to fetch subject details', err);
      toast.error('An error occurred while loading subject details');
    } finally {
      setAdminDetailLoading(false);
    }
  };

  useEffect(() => {
    if (!authChecked) return;
    fetchUsers();
    fetchSubjects();
    fetchAllAssignments();
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
      const response = await fetch(`${apiBase}/api/v1/qc/subjects-list`, { headers: authHeaders });
      if (response.status === 401) {
        toast.error('Session expired, please log in again');
        navigate('/qc-bcd-login');
        return;
      }
      if (!response.ok) throw new Error('Failed to fetch subjects');
      const data = await response.json();
      const list = Array.isArray(data?.subjects) ? data.subjects : [];
      setSubjects(list);
      setTotalSubjects(typeof data?.total === 'number' ? data.total : list.length);
    } catch (err) {
      console.error('Failed to fetch subjects', err);
      toast.error('Failed to load subjects list');
    } finally {
      setSubjectsLoading(false);
    }
  };

  const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  const handleCreateClick = () => {
    const trimmedEmail = email.trim();
    const trimmedName = fullName.trim();

    if (!trimmedName || !trimmedEmail || !password || selectedSubjects.length === 0) {
      toast.error('Please enter full name, email, password, and select at least one subject');
      return;
    }

    if (!EMAIL_REGEX.test(trimmedEmail)) {
      toast.error('Please enter a valid email address');
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
          full_name: fullName.trim(),
          email: email.trim(),
          password: password,
          role: 'QC Radiologist',
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
        setFullName('');
        setEmail('');
        setPassword('');
        setSelectedSubjects([]);
        fetchAllAssignments();
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

  const fetchAllAssignments = async () => {
    setAllAssignmentsLoading(true);
    try {
      const response = await fetch(`${apiBase}/api/v1/qc/admin/all/assignments`, { headers: authHeaders });
      if (response.status === 401) {
        toast.error('Session expired, please log in again');
        navigate('/qc-bcd-login');
        return;
      }
      if (!response.ok) throw new Error('Failed to fetch assignments');
      const data = await response.json();
      setAllAssignments(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Failed to fetch assignments', err);
      toast.error('Failed to load assignments');
    } finally {
      setAllAssignmentsLoading(false);
    }
  };

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

      <div style={{ marginTop: '20px' ,backgroundColor: '#F3FAF8',padding: '20px', borderRadius: '8px'}}>
        <div style={cardStyle}>
          <div style={cardHeaderStyle}>Create New Study</div>
          <div style={fieldWrapStyle}>
            <div style={fieldGroupStyle}>
              <label style={labelStyle}>Full Name</label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Dr. Jane Doe"
                autoComplete="off"
                name="qc-assign-fullname"
                style={ddTriggerStyle}
              />
            </div>

            <div style={fieldGroupStyle}>
              <label style={labelStyle}>User Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="user@example.com"
                autoComplete="off"
                name="qc-assign-email"
                style={ddTriggerStyle}
              />
            </div>

            <div style={fieldGroupStyle}>
              <label style={labelStyle}>Password</label>
              <div style={{ position: 'relative' }}>
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Set login password for this user"
                  autoComplete="new-password"
                  name="qc-assign-password"
                  style={{ ...ddTriggerStyle, paddingRight: '38px' }}
                />
                <span
                  onClick={() => setShowPassword((s) => !s)}
                  style={{
                    position: 'absolute',
                    right: '12px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    cursor: 'pointer',
                    fontSize: '15px'
                  }}
                >
                  {showPassword ? '🙈' : '👁️'}
                </span>
              </div>
            </div>

            <div style={fieldGroupStyle}>
              <label style={labelStyle}>Assign Subjects</label>
              <SearchableDropdown
                options={subjects}
                getValue={(s) => String(s.qc_id)}
                getLabel={(s) => s.display_id}
                getDisabled={(s) => s.is_assigned}
                multiple={true}
                selected={selectedSubjects}
                onChange={setSelectedSubjects}
                placeholder="Select Subjects"
                loading={subjectsLoading}
                emptyText="No subjects found"
              />
              <div style={{ marginTop: '6px', fontSize: '12.5px', color: '#555' }}>
                Total Subjects: {subjectsLoading ? '…' : totalSubjects}
              </div>
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

      <div
        style={{
          maxHeight: '80vh',
          overflowY: 'auto',
          overflowX: 'auto',
          border: '1px solid #dee2e6',
          borderRadius: '6px',
        }}
      >
        <table
          style={{
            width: '100%',
            borderCollapse: 'collapse',
            minWidth: '1000px',
            backgroundColor: '#fff',
            border: '1px solid #dee2e6',
          }}
        >
          <thead>
            <tr>
              <th style={{ ...qcThStyle, position: 'sticky', top: 0, zIndex: 1 }}>
                Subject ID
              </th>
              <th style={{ ...qcThStyle, position: 'sticky', top: 0, zIndex: 1 }}>
                Radiologist
              </th>
              <th style={{ ...qcThStyle, position: 'sticky', top: 0, zIndex: 1 }}>
                Email
              </th>
              <th style={{ ...qcThStyle, position: 'sticky', top: 0, zIndex: 1 }}>
                Hospital
              </th>
              <th style={{ ...qcThStyle, position: 'sticky', top: 0, zIndex: 1 }}>
                Risk
              </th>
              <th style={{ ...qcThStyle, position: 'sticky', top: 0, zIndex: 1 }}>
                Assessment
              </th>
              <th style={{ ...qcThStyle, position: 'sticky', top: 0, zIndex: 1 }}>
                Status
              </th>
              <th style={{ ...qcThStyle, position: 'sticky', top: 0, zIndex: 1 }}>
                Assigned At
              </th>
            </tr>
          </thead>

          <tbody>
            {allAssignments.map((a) => (
              <tr
                key={a.qc_assignment_id}
                style={{
                  borderBottom: '1px solid #dee2e6',
                }}
              >
                <td style={qcTdStyle}>{a.display_id || a.id?.substring(0, 8)}</td>
                <td style={qcTdStyle}>{a.radiologist_name || '—'}</td>
                <td style={qcTdStyle}>{a.radiologist_email}</td>
                <td style={{ ...qcTdStyle, fontSize: 12 }}>
                  {a.qc_short_name || '-'}
                </td>

                <td style={qcTdStyle}>
                  {a.risk_category ? (
                    <span
                      style={{
                        display: 'inline-block',
                        padding: '4px 12px',
                        borderRadius: 12,
                        fontSize: 12,
                        fontWeight: 600,
                        backgroundColor: RISK_COLORS[a.risk_category] || '#eee',
                        color: '#111',
                      }}
                    >
                      {a.risk_category.replace(' Risk', '')}
                    </span>
                  ) : (
                    '-'
                  )}
                </td>

                <td style={statusCellStyle(a.has_assessment)}>
                  {a.has_assessment ? 'Yes' : 'No'}
                </td>

                <td style={qcTdStyle}>
                  <span
                    style={{
                      padding: '3px 10px',
                      borderRadius: '12px',
                      fontSize: '12px',
                      fontWeight: 600,
                      backgroundColor:
                        a.qc_status === 'Completed' ? '#DFF5E1' : '#FFF3D6',
                      color:
                        a.qc_status === 'Completed' ? '#1E7B34' : '#8A6D00',
                    }}
                  >
                    {a.qc_status}
                  </span>
                </td>

                <td style={qcTdStyle}>
                  {a.qc_assigned_at
                    ? new Date(a.qc_assigned_at).toLocaleString()
                    : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {isAdminModalOpen && selectedAdminSubject && (
        <div style={modalOverlayStyle} onClick={() => setIsAdminModalOpen(false)}>
          <div
            style={{ backgroundColor: '#fff', width: '80%', maxWidth: '90vw', maxHeight: '80vh', borderRadius: '8px', display: 'flex', flexDirection: 'column', boxShadow: '0 5px 15px rgba(0,0,0,0.3)' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ padding: '15px 20px', borderBottom: '1px solid #dee2e6', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3>Responses for Subject ID: {selectedAdminSubject.patient_id || selectedAdminSubject.id}</h3>
              <button style={{ background: 'none', border: 'none', fontSize: '24px', cursor: 'pointer', color: '#666' }} onClick={() => setIsAdminModalOpen(false)}>&times;</button>
            </div>
            <div style={{ padding: '20px', overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: 'left', padding: '10px', borderBottom: '2px solid #dee2e6', backgroundColor: '#f8f9fa' }}>Question</th>
                    <th style={{ textAlign: 'left', padding: '10px', borderBottom: '2px solid #dee2e6', backgroundColor: '#f8f9fa' }}>Answer</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedAdminSubject.responses && selectedAdminSubject.responses.length > 0 ? (
                    selectedAdminSubject.responses.map((resp) => (
                      <tr key={resp.id}>
                        <td style={{ padding: '10px', borderBottom: '1px solid #eee' }}>{resp.question}</td>
                        <td style={{ padding: '10px', borderBottom: '1px solid #eee' }}>{resp.answer}</td>
                      </tr>
                    ))
                  ) : (
                    <tr><td colSpan="2" style={{ padding: '10px', borderBottom: '1px solid #eee' }}>No responses found for this session.</td></tr>
                  )}
                </tbody>
              </table>
              {!selectedAdminSubject.assessment && (
                <div style={{ marginTop: 16, padding: '10px 16px', borderRadius: 6, backgroundColor: '#f0f4ff', border: '1px solid #c8d8f8', color: '#3a5a9e', fontSize: 13 }}>
                  No assessment has been submitted for this subject yet.
                </div>
              )}
            </div>
          </div>
        </div>
      )}
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