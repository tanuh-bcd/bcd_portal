import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import DoctorAssessmentForm from '../components/DoctorAssessmentForm';

const DoctorPage = ({ isEmbedded = false }) => {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedSession, setSelectedSession] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [sortStack, setSortStack] = useState([{ key: 'date', dir: 'desc' }]);

  useEffect(() => {
    if (!isEmbedded) {
      const role = localStorage.getItem('role')?.toLowerCase();
      const token = localStorage.getItem('token');
      if (!token || (role !== 'clinician' && role !== 'admin')) {
        navigate('/login');
        return;
      }
    }
    fetchSessions();
  }, [navigate, isEmbedded]);

  const fetchSessions = async (sortParam) => {
    try {
      setLoading(true);
      const token = localStorage.getItem('token');
      if (!token) {
        setError('Authentication token missing. Please log in again.');
        setLoading(false);
        return;
      }
      const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
      const sortQuery = sortParam || sortStack.map(s => `${s.key}:${s.dir}`).join(',');
      const response = await fetch(`${apiUrl}/api/v1/doctor/sessions?sort=${encodeURIComponent(sortQuery)}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setSessions(data);
      } else {
        const contentType = response.headers.get("content-type");
        if (contentType && contentType.indexOf("application/json") !== -1) {
          const errorData = await response.json();
          setError(errorData.detail || 'Failed to fetch sessions');
        } else {
          const errorText = await response.text();
          console.error("Non-JSON error response:", errorText);
          setError(`Server error: ${response.status}`);
        }
      }
    } catch (err) {
      setError('An error occurred while fetching sessions');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const fetchSessionDetail = async (sessionId) => {
    try {
      const token = localStorage.getItem('token');
      if (!token) {
        alert('Authentication token missing. Please log in again.');
        return;
      }
      const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/v1/doctor/sessions/${sessionId}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setSelectedSession(data);
        setIsModalOpen(true);
      } else {
        const contentType = response.headers.get("content-type");
        if (contentType && contentType.indexOf("application/json") !== -1) {
          const errorData = await response.json();
          alert(`Failed to fetch session details: ${errorData.detail || 'Unknown error'}`);
        } else {
          const errorText = await response.text();
          console.error("Non-JSON error response:", errorText);
          alert(`Server error: ${response.status}`);
        }
      }
    } catch (err) {
      console.error(err);
      alert('An error occurred while fetching session details');
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    localStorage.removeItem('hospitalName');
    localStorage.removeItem('userEmail');
    localStorage.removeItem('userName');
    navigate('/login');
  };

  const convertGcsToHttp = (gcsUrl) => {
    if (!gcsUrl) return null;
    if (gcsUrl.startsWith('gs://')) {
      const path = gcsUrl.replace('gs://', '');
      return `https://storage.googleapis.com/${path}`;
    }
    return gcsUrl;
  };

  const RISK_COLORS = { 'Baseline Risk': '#6ee7b7', 'Evident Risk': '#fde047', 'Significant Risk': '#fb923c', 'High Risk': '#fb7185' };

  const handleSort = (key) => {
    setSortStack(prev => {
      const existing = prev.find(s => s.key === key);
      let newStack;
      if (existing) {
        newStack = prev.map(s => s.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : s);
      } else {
        newStack = [...prev, { key, dir: 'asc' }];
        if (newStack.length > 3) newStack = newStack.slice(-3);
      }
      const sortQuery = newStack.map(s => `${s.key}:${s.dir}`).join(',');
      fetchSessions(sortQuery);
      return newStack;
    });
  };

  const clearSort = () => {
    const defaultSort = [{ key: 'date', dir: 'desc' }];
    setSortStack(defaultSort);
    fetchSessions('date:desc');
  };

  const sortArrow = (key) => {
    const entry = sortStack.find(s => s.key === key);
    if (!entry) return ' ⇅';
    const pos = sortStack.indexOf(entry) + 1;
    const arrow = entry.dir === 'asc' ? '↑' : '↓';
    return ` ${arrow}${sortStack.length > 1 ? pos : ''}`;
  };

  const content = (
    <div style={contentStyle}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ color: '#333', margin: 0 }}>Subject List</h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {sortStack.map((s, i) => (
            <span key={i} style={{ fontSize: 12, padding: '3px 10px', borderRadius: 12, backgroundColor: '#e8f7f8', color: '#14868C', fontWeight: 600 }}>
              {s.key}{s.dir === 'asc' ? '↑' : '↓'}
            </span>
          ))}
          {sortStack.length > 1 && (
            <button onClick={clearSort} style={{ fontSize: 11, padding: '3px 10px', borderRadius: 12, border: '1px solid #ccc', background: '#fff', cursor: 'pointer', color: '#666' }}>
              Clear
            </button>
          )}
        </div>
      </div>

      {loading && <p>Loading sessions...</p>}
      {error && <p style={{ color: 'red' }}>{error}</p>}

      {!loading && !error && sessions.length === 0 && <p>No sessions found.</p>}
      
      {!loading && !error && sessions.length > 0 && (
        <div style={tableContainerStyle}>
          <table style={tableStyle}>
            <thead>
              <tr style={headerRowStyle}>
                <th style={thCenterStyle}>Patient ID</th>
                <th style={sortableThStyle} onClick={() => handleSort('date')}>Date{sortArrow('date')}</th>
                <th style={thCenterStyle}>Risk</th>
                <th style={sortableThStyle} onClick={() => handleSort('assessment')}>Assessment{sortArrow('assessment')}</th>
                <th style={thCenterStyle}>Mammo DICOM</th>
                <th style={thCenterStyle}>Mammo Report</th>
                <th style={thCenterStyle}>Sonogram</th>
                <th style={thCenterStyle}>Sonogram Report</th>
                <th style={thCenterStyle}>Biopsy</th>
                <th style={thCenterStyle}>Annotations</th>
                <th style={thCenterStyle}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((session) => (
                <tr key={session.id} style={rowStyle}>
                  <td style={{ ...tdStyle, textAlign: 'center' }}>{session.patient_id || session.id?.substring(0, 8)}</td>
                  <td style={{ ...tdStyle, textAlign: 'center', fontSize: 12 }}>{session.consent_timestamp ? new Date(session.consent_timestamp).toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: 'numeric' }) : '-'}</td>
                  <td style={{ ...tdStyle, textAlign: 'center' }}>
                    {session.risk_category ? (
                      <span style={{
                        display: 'inline-block',
                        padding: '4px 12px',
                        borderRadius: 12,
                        fontSize: 12,
                        fontWeight: 600,
                        backgroundColor: RISK_COLORS[session.risk_category] || '#eee',
                        color: '#111',
                      }}>{session.risk_category.replace(' Risk', '')}</span>
                    ) : '-'}
                  </td>
                  <td style={statusCellStyle(session.has_assessment)}>
                    {session.has_assessment ? 'Yes' : 'No'}
                  </td>
                  <td style={statusCellStyle(session.has_mammo_dicom)}>
                    {session.has_mammo_dicom ? 'Yes' : 'No'}
                  </td>
                  <td style={statusCellStyle(session.has_mammo_reading)}>
                    {session.has_mammo_reading ? 'Yes' : 'No'}
                  </td>
                  <td style={statusCellStyle(session.has_us_video)}>
                    {session.has_us_video ? 'Yes' : 'No'}
                  </td>
                  <td style={statusCellStyle(session.has_us_reading)}>
                    {session.has_us_reading ? 'Yes' : 'No'}
                  </td>
                  <td style={statusCellStyle(session.has_biopsy)}>
                    {session.has_biopsy ? 'Yes' : 'No'}
                  </td>
                  <td style={statusCellStyle(session.has_annotations)}>
                    {session.has_annotations ? 'Yes' : 'No'}
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'center' }}>
                    <button
                      onClick={() => fetchSessionDetail(session.id)}
                      style={linkButtonStyle}
                    >
                      {session.has_assessment ? 'Edit Assessment' : 'View Responses'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {isModalOpen && selectedSession && (
        <div style={modalOverlayStyle} onClick={() => setIsModalOpen(false)}>
          <div style={modalContentStyle} onClick={(e) => e.stopPropagation()}>
            <div style={modalHeaderStyle}>
              <h3>Responses for Patient ID: {selectedSession.id}</h3>
              <button style={closeButtonStyle} onClick={() => setIsModalOpen(false)}>&times;</button>
            </div>
            <div style={modalBodyStyle}>
              <table style={qaTableStyle}>
                <thead>
                  <tr>
                    <th style={qaThStyle}>Question</th>
                    <th style={qaThStyle}>Answer</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedSession.responses && selectedSession.responses.length > 0 ? (
                    selectedSession.responses.map((resp) => (
                      <tr key={resp.id}>
                        <td style={qaTdStyle}>{resp.question}</td>
                        <td style={qaTdStyle}>{resp.answer}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan="2" style={qaTdStyle}>No responses found for this session.</td>
                    </tr>
                  )}
                </tbody>
              </table>
              
              <DoctorAssessmentForm
                sessionId={selectedSession.id}
                initialData={selectedSession.assessment}
                snehithaRisk={(() => {
                  if (!selectedSession.responses) return null;
                  const r = {};
                  selectedSession.responses.forEach(resp => { r[resp.question] = resp.answer; });
                  const age = parseInt(r['What is your current age? (Please enter a number - years)'] || r['Q1'] || '0') || 0;
                  const aam = parseInt(r['What age were you when you had your first menstrual period? (Please enter a number)'] || r['Q10'] || '0') || 0;
                  const irr = (r['Q12_Current'] === 'No' || r['Are your menstrual cycles regular? - Currently'] === 'No') ? 1 : 0;
                  const bf = (r['Q17'] === 'greater than 24 months' || r['For how long did you breastfeed?'] === 'greater than 24 months') ? 1 : 0;
                  const fh = (r['Q21'] === 'First Order (Mother, Sibling, Father)' || (r['Has anyone in your family been diagnosed with any type of cancer?'] || '').includes('First')) ? 1 : 0;
                  const bx = (r['Q40'] === 'Yes' || r['Have you had a breast biopsy?'] === 'Yes') ? 1 : 0;
                  const nul = (r['Q14'] === 'No' || r['Have you given birth to a child?'] === 'No') ? 1 : 0;
                  const a25 = (r['Q16'] === '25 to 29') ? 1 : 0;
                  const a30 = (r['Q16'] === 'After 30') ? 1 : 0;
                  const ab = (nul || a25) ? 1 : 0;
                  const lp = -0.940 + 0.027*age - 0.082*aam + 0.453*irr - 0.892*bf + 0.810*fh + 1.420*bx + 0.811*ab + 1.035*a30;
                  return ((1 / (1 + Math.exp(-lp))) * 100).toFixed(2);
                })()}
                onSaveSuccess={() => {
                  fetchSessions();
                  setTimeout(() => setIsModalOpen(false), 2000);
                }}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );

  if (isEmbedded) {
    return content;
  }

  return (
    <Layout 
      userRole="clinician" 
      handleLogout={handleLogout} 
      fullWidth={true}
    >
      {content}
    </Layout>
  );
};

const contentStyle = {
  backgroundColor: '#fff',
  padding: '20px',
  minHeight: '400px',
};

const tableContainerStyle = {
  overflowX: 'auto'
};

const tableStyle = {
  width: '100%',
  borderCollapse: 'collapse',
  marginTop: '10px'
};

const headerRowStyle = {
  backgroundColor: '#f8f9fa',
  borderBottom: '2px solid #dee2e6'
};

const thStyle = {
  padding: '12px',
  textAlign: 'left',
  color: '#495057',
  fontWeight: '600'
};

const thCenterStyle = {
  padding: '12px',
  textAlign: 'center',
  color: '#495057',
  fontWeight: '600'
};

const sortableThStyle = {
  padding: '12px',
  textAlign: 'center',
  color: '#14868C',
  fontWeight: '600',
  cursor: 'pointer',
  userSelect: 'none',
};

const statusCellStyle = (isTrue) => ({
  padding: '12px',
  verticalAlign: 'middle',
  textAlign: 'center',
  color: isTrue ? 'green' : 'red',
  fontWeight: 'bold',
});

const rowStyle = {
  borderBottom: '1px solid #dee2e6'
};

const tdStyle = {
  padding: '12px',
  verticalAlign: 'middle'
};

const thumbnailStyle = {
  width: '50px',
  height: '50px',
  objectFit: 'cover',
  borderRadius: '4px',
  cursor: 'pointer',
  border: '1px solid #ddd'
};

const linkButtonStyle = {
  background: 'none',
  border: 'none',
  color: '#14868C',
  textDecoration: 'underline',
  cursor: 'pointer',
  padding: '0',
  fontSize: '14px'
};

const modalOverlayStyle = {
  position: 'fixed',
  top: '0',
  left: '0',
  right: '0',
  bottom: '0',
  backgroundColor: 'rgba(0,0,0,0.5)',
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'center',
  zIndex: 1000
};

const modalContentStyle = {
  backgroundColor: '#fff',
  width: '80%',
  maxWidth: '800px',
  maxHeight: '80vh',
  borderRadius: '8px',
  display: 'flex',
  flexDirection: 'column',
  boxShadow: '0 5px 15px rgba(0,0,0,0.3)'
};

const modalHeaderStyle = {
  padding: '15px 20px',
  borderBottom: '1px solid #dee2e6',
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center'
};

const modalBodyStyle = {
  padding: '20px',
  overflowY: 'auto'
};

const closeButtonStyle = {
  background: 'none',
  border: 'none',
  fontSize: '24px',
  cursor: 'pointer',
  color: '#666'
};

const qaTableStyle = {
  width: '100%',
  borderCollapse: 'collapse'
};

const qaThStyle = {
  textAlign: 'left',
  padding: '10px',
  borderBottom: '2px solid #dee2e6',
  backgroundColor: '#f8f9fa'
};

const qaTdStyle = {
  padding: '10px',
  borderBottom: '1px solid #eee'
};

export default DoctorPage;
