import React, { useState, useEffect, useRef } from 'react';

const newBadgeStyle = {
  fontSize: '11px',
  fontWeight: 'bold',
  color: '#14868C',
  backgroundColor: '#DCF3EF',
  padding: '2px 8px',
  borderRadius: '10px',
  letterSpacing: '0.3px'
};

const kappaBadgeStyle = (score) => {
  let bg = '#F1F3F5', color = '#495057';
  if (score !== null && score !== undefined) {
    if (score >= 0.61) { bg = '#E3F5E9'; color = '#1E7E4B'; }
    else if (score >= 0.21) { bg = '#FDF0DA'; color = '#B0691C'; }
    else { bg = '#FBE3E1'; color = '#C4302B'; }
  }
  return {
    display: 'inline-block',
    padding: '3px 10px',
    borderRadius: '6px',
    fontSize: '13px',
    fontWeight: 600,
    backgroundColor: bg,
    color
  };
};

const dropdownFieldStyle = {
  width: '100%',
  padding: '10px 12px',
  borderRadius: '6px',
  border: '1px solid #cfd8dc',
  backgroundColor: 'white',
  fontSize: '14px',
  marginBottom: '14px',
  cursor: 'pointer',
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  userSelect: 'none',
  position: 'relative'
};

const dropdownPanelStyle = {
  position: 'absolute',
  top: 'calc(100% + 4px)',
  left: 0,
  right: 0,
  backgroundColor: 'white',
  border: '1px solid #cfd8dc',
  borderRadius: '6px',
  boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
  zIndex: 10,
  maxHeight: '220px',
  overflowY: 'auto'
};

const dropdownOptionStyle = {
  padding: '10px 12px',
  fontSize: '14px',
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  gap: '10px'
};

const clearOptionStyle = {
  padding: '10px 12px',
  fontSize: '13px',
  cursor: 'pointer',
  color: '#C4302B',
  fontWeight: 600,
  borderBottom: '1px solid #eee'
};

// options/selected work with {id, full_name} objects, compared by id
const ReaderMultiSelect = ({ options, selected, onChange }) => {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const isSelected = (id) => selected.some((u) => u.id === id);

  const toggleOption = (user) => {
    if (isSelected(user.id)) {
      onChange(selected.filter((u) => u.id !== user.id));
    } else {
      onChange([...selected, user]);
    }
  };

  const label = selected.length === 0
    ? 'Assign readers *'
    : selected.length === 1
      ? selected[0].full_name
      : `${selected.length} readers selected`;

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <div style={dropdownFieldStyle} onClick={() => setOpen(!open)}>
        <span style={{ color: selected.length === 0 ? '#8a97a0' : '#1a1a1a' }}>{label}</span>
        <span style={{ fontSize: '11px', color: '#666' }}>▾</span>
      </div>
      {open && (
        <div style={dropdownPanelStyle}>
          {selected.length > 0 && (
            <div style={clearOptionStyle} onClick={() => { onChange([]); setOpen(false); }}>
              Clear selection
            </div>
          )}
          {options.map((user) => (
            <label key={user.id} style={dropdownOptionStyle}>
              <input
                type="checkbox"
                checked={isSelected(user.id)}
                onChange={() => toggleOption(user)}
              />
              {user.full_name}
            </label>
          ))}
          {options.length === 0 && (
            <div style={{ padding: '10px 12px', fontSize: '13px', color: '#999' }}>
              No clinicians available
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const ArbiterSelect = ({ options, selected, onChange }) => {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <div style={dropdownFieldStyle} onClick={() => setOpen(!open)}>
        <span style={{ color: selected ? '#1a1a1a' : '#8a97a0' }}>
          {selected ? selected.full_name : 'Assign arbiter *'}
        </span>
        <span style={{ fontSize: '11px', color: '#666' }}>▾</span>
      </div>
      {open && (
        <div style={dropdownPanelStyle}>
          {selected && (
            <div style={clearOptionStyle} onClick={() => { onChange(null); setOpen(false); }}>
              Clear selection
            </div>
          )}
          {options.map((user) => (
            <div
              key={user.id}
              style={dropdownOptionStyle}
              onClick={() => { onChange(user); setOpen(false); }}
            >
              {user.full_name}
            </div>
          ))}
          {options.length === 0 && (
            <div style={{ padding: '10px 12px', fontSize: '13px', color: '#999' }}>
              No clinicians available
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const AgreementInfoPopover = () => {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const iconStyle = { cursor: 'pointer', color: '#14868C', marginLeft: '4px' };

  const popoverStyle = {
    position: 'absolute',
    top: 'calc(100% + 8px)',
    right: 0,
    width: '320px',
    backgroundColor: '#EAF2FB',
    border: '1px solid #CFE0F5',
    borderRadius: '8px',
    padding: '16px 18px',
    boxShadow: '0 6px 16px rgba(0,0,0,0.12)',
    zIndex: 20,
    fontWeight: 'normal',
    textAlign: 'left'
  };

  return (
    <span ref={ref} style={{ position: 'relative', display: 'inline-block' }}>
      <span style={iconStyle} onClick={() => setOpen(!open)}>ⓘ</span>
      {open && (
        <div style={popoverStyle}>
          <p style={{ fontWeight: 'bold', color: '#1d4e89', marginBottom: '8px' }}>What is Agreement?</p>
          <p style={{ marginBottom: '8px', color: '#333', fontSize: '13px' }}>
            Agreement (kappa score) measures how much the reader's assessments agree with the consensus (or arbiter) beyond chance. It ranges from -1 to 1, where:
          </p>
          <ul style={{ margin: '0 0 8px 18px', color: '#333', fontSize: '13px' }}>
            <li>1 = Perfect agreement</li>
            <li>0 = Agreement equivalent to chance</li>
            <li>&lt; 0 = Less agreement than chance</li>
          </ul>
          <p style={{ color: '#333', fontSize: '13px' }}>Higher values indicate better consistency and reliability of the reader.</p>
        </div>
      )}
    </span>
  );
};

const MRMCStudyContent = () => {
  const [expanded, setExpanded] = useState(true);
  const [studyName, setStudyName] = useState('');
  const [selectedReaders, setSelectedReaders] = useState([]);
  const [selectedArbiter, setSelectedArbiter] = useState(null);

  const [clinicians, setClinicians] = useState([]);
  const [cliniciansLoading, setCliniciansLoading] = useState(true);

  const [creating, setCreating] = useState(false);
  const [activeStudy, setActiveStudy] = useState(null); // { id, name }
  const [participants, setParticipants] = useState([]);
  const [participantsLoading, setParticipantsLoading] = useState(false);

  const readerOptions = clinicians.filter((u) => u.id !== selectedArbiter?.id);
  const arbiterOptions = clinicians.filter((u) => !selectedReaders.some((r) => r.id === u.id));

  useEffect(() => {
    fetchClinicians();
    fetchParticipants();
  }, []);

  const fetchClinicians = async () => {
    setCliniciansLoading(true);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(
        `${process.env.REACT_APP_API_URL || ''}/api/v1/admin/users/clinicians`,
        { headers: { 'Authorization': `Bearer ${token}` } }
      );
      const contentType = response.headers.get('content-type');
      if (response.ok && contentType && contentType.indexOf('application/json') !== -1) {
        const data = await response.json();
        if (Array.isArray(data)) {
          setClinicians(data);
        } else {
          console.error('Clinicians data is not an array:', data);
          alert('Error: Received invalid data format for clinicians.');
        }
      } else {
        const text = await response.text();
        console.error('Failed to fetch clinicians:', text);
        alert(`Error: Failed to fetch clinicians list. Status: ${response.status}`);
      }
    } catch (err) {
      console.error('Failed to fetch clinicians', err);
      alert('Error: Network error while fetching clinicians.');
    } finally {
      setCliniciansLoading(false);
    }
  };

  const fetchParticipants = async () => {
    setParticipantsLoading(true);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(
        `${process.env.REACT_APP_API_URL || ''}/api/v1/admin/mrmc-studies/participants`,
        { headers: { 'Authorization': `Bearer ${token}` } }
      );
      const contentType = response.headers.get('content-type');
      if (response.ok && contentType && contentType.indexOf('application/json') !== -1) {
        const data = await response.json();
        setParticipants(Array.isArray(data) ? data : []);
      } else {
        const text = await response.text();
        console.error('Failed to fetch participants:', text);
        alert(`Error: Failed to fetch reader panel. Status: ${response.status}`);
      }
    } catch (err) {
      console.error('Failed to fetch participants', err);
      alert('Error: Network error while fetching reader panel.');
    } finally {
      setParticipantsLoading(false);
    }
  };

  const handleCreateStudy = async () => {
    if (!studyName.trim()) {
      alert('Error: Study name is required.');
      return;
    }
    if (selectedReaders.length === 0) {
      alert('Error: At least one reader must be assigned.');
      return;
    }
    if (!selectedArbiter) {
      alert('Error: An arbiter must be assigned.');
      return;
    }

    setCreating(true);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${process.env.REACT_APP_API_URL || ''}/api/v1/admin/mrmc-studies`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          name: studyName,
          reader_user_ids: selectedReaders.map((u) => u.id),
          arbiter_user_id: selectedArbiter.id
        })
      });

      if (response.ok) {
        const data = await response.json();
        alert('MRMC study created successfully!');
        setActiveStudy({ id: data.id, name: data.name });
        setStudyName('');
        setSelectedReaders([]);
        setSelectedArbiter(null);
        fetchParticipants();
      } else {
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.indexOf('application/json') !== -1) {
          const error = await response.json();
          const detail = error.detail;
          const message = Array.isArray(detail)
            ? detail.map((d) => d.msg || JSON.stringify(d)).join('; ')
            : (detail || 'Failed to create study');
          alert(`Error: ${message}`);
        } else {
          const errorText = await response.text();
          console.error('Non-JSON error response:', errorText);
          alert(`Error: Received non-JSON response from server. Status: ${response.status}`);
        }
      }
    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      setCreating(false);
    }
  };

  const cardStyle = {
    border: '1px solid #B7E0D8',
    borderRadius: '8px',
    backgroundColor: '#F3FAF8',
    marginBottom: '30px'
  };

  const cardHeaderStyle = {
    padding: '18px 20px',
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    justifyContent: 'space-between',
    cursor: 'pointer',
    fontWeight: 'bold',
    fontSize: '17px',
    color: '#1a1a1a',
    borderRadius: '8px 8px 0 0'
  };

  const fieldWrapStyle = { padding: '0 20px 20px' };

  const inputFieldStyle = {
    width: '100%',
    padding: '10px 12px',
    borderRadius: '6px',
    border: '1px solid #cfd8dc',
    backgroundColor: 'white',
    fontSize: '14px',
    marginBottom: '14px',
    boxSizing: 'border-box'
  };

  return (
    <div>
      <div style={cardStyle}>
        <div style={cardHeaderStyle} onClick={() => setExpanded(!expanded)}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            Create MRMC study
          </span>
          <span>{expanded ? '−' : '+'}</span>
        </div>
        {expanded && (
          <div style={fieldWrapStyle}>
            <input
              style={inputFieldStyle}
              placeholder="Study name *"
              value={studyName}
              onChange={(e) => setStudyName(e.target.value)}
            />
            {cliniciansLoading ? (
              <p style={{ color: '#666', fontSize: '14px', marginBottom: '14px' }}>Loading clinicians...</p>
            ) : (
              <>
                <ReaderMultiSelect options={readerOptions} selected={selectedReaders} onChange={setSelectedReaders} />
                {/* <ArbiterSelect options={arbiterOptions} selected={selectedArbiter} onChange={setSelectedArbiter} /> */}
              </>
            )}
            <button
              style={{
                padding: '10px 20px',
                backgroundColor: '#14868C',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
                fontWeight: 'bold',
                opacity: creating ? 0.7 : 1
              }}
              disabled={creating || cliniciansLoading}
              onClick={handleCreateStudy}
            >
              {creating ? 'Creating...' : 'Create New Study'}
            </button>
          </div>
        )}
      </div>

      <>
        <h3 style={{ color: '#14868C', marginBottom: '16px' }}>
          Admin — reader panel
        </h3>
        {participantsLoading ? (
          <p style={{ color: '#666' }}>Loading reader panel...</p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '30px' }}>
            <thead>
              <tr style={{ textAlign: 'left', borderBottom: '2px solid #e0e0e0' }}>
                {['Reader', 'Role', 'Assigned', 'Submitted'].map((h) => (
                  <th key={h} style={{ padding: '10px 12px', fontSize: '14px', color: '#333' }}>{h}</th>
                ))}
                <th style={{ padding: '10px 12px', fontSize: '14px', color: '#333', position: 'relative' }}>
                  Agreement
                  <AgreementInfoPopover />
                </th>
              </tr>
            </thead>
            <tbody>
             {participants.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ padding: '20px 12px', textAlign: 'center', color: '#999', fontSize: '14px' }}>
                    No participants yet.
                  </td>
                </tr>
              ) : (
                participants.map((row) => {
                  const roleLabel = [
                    row.is_reader ? 'Reader' : null,
                    row.is_arbiter ? 'Arbiter' : null
                  ].filter(Boolean).join(', ');

                  return (
                    <tr key={row.user_id} style={{ borderBottom: '1px solid #eee' }}>
                      <td style={{ padding: '12px' }}>{row.full_name}</td>
                      <td style={{ padding: '12px' }}>{roleLabel}</td>
                      <td style={{ padding: '12px' }}>{row.assigned_count}</td>
                      <td style={{ padding: '12px' }}>{row.submitted_count}</td>
                      <td style={{ padding: '12px' }}>
                        {row.kappa_score !== null && row.kappa_score !== undefined
                          ? <span style={kappaBadgeStyle(row.kappa_score)}>{row.kappa_score.toFixed(2)} κ</span>
                          : '—'}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        )}
      </>
    </div>
  );
};

export default MRMCStudyContent;