import React, { useState, useEffect } from 'react';
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

const fieldGroupStyle = { marginBottom: '16px' };

const labelStyle = {
  display: 'block',
  marginBottom: '6px',
  fontWeight: 500,
  fontSize: '14px',
  color: '#333'
};

const selectStyle = {
  width: '100%',
  padding: '10px 12px',
  borderRadius: '6px',
  border: '1px solid #cfd8dc',
  backgroundColor: 'white',
  fontSize: '14px',
  boxSizing: 'border-box'
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
  const [selectedSubject, setSelectedSubject] = useState('');

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
    if (!selectedUser || !selectedSubject) {
      toast.error('Please select both a user and a subject');
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
          assessment_id: Number(selectedSubject),
          radiologist_id: Number(selectedUser)
        })
      });
      const data = await response.json();
      if (response.ok) {
        toast.success('Study created successfully');
        setSelectedUser('');
        setSelectedSubject('');
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
              <select
                style={selectStyle}
                value={selectedUser}
                onChange={(e) => setSelectedUser(e.target.value)}
                disabled={usersLoading}
              >
                <option value="">{usersLoading ? 'Loading users...' : 'Select User'}</option>
                {users.map((u) => (
                  <option key={u.qc_id} value={u.qc_id}>
                    {u.qc_full_name || u.qc_email}
                  </option>
                ))}
              </select>
            </div>

            <div style={fieldGroupStyle}>
              <label style={labelStyle}>Assign Subject</label>
              <select
                style={selectStyle}
                value={selectedSubject}
                onChange={(e) => setSelectedSubject(e.target.value)}
                disabled={subjectsLoading}
              >
                <option value="">{subjectsLoading ? 'Loading subjects...' : 'Select Subject'}</option>
                {subjects.map((s) => (
                  <option key={s.qc_id} value={s.qc_id}>
                    {s.display_id}
                  </option>
                ))}
              </select>
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
            <p>Create this study with the selected user and subject?</p>
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