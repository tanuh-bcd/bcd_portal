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

  useEffect(() => {
    if (!isEmbedded) {
      const role = localStorage.getItem('role')?.toLowerCase();
      const token = localStorage.getItem('token');
      if (!token || (role !== 'doctor' && role !== 'admin')) {
        navigate('/login');
        return;
      }
    }
    fetchSessions();
  }, [navigate, isEmbedded]);

  const fetchSessions = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('token');
      if (!token) {
        setError('Authentication token missing. Please log in again.');
        setLoading(false);
        return;
      }
      const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/v1/doctor/sessions`, {
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

  const content = (
    <div style={contentStyle}>
      <h2 style={{ color: '#333', marginBottom: '20px' }}>Patient List</h2>
      
      {loading && <p>Loading sessions...</p>}
      {error && <p style={{ color: 'red' }}>{error}</p>}
      
      {!loading && !error && sessions.length === 0 && <p>No patient sessions found.</p>}
      
      {!loading && !error && sessions.length > 0 && (
        <div style={tableContainerStyle}>
          <table style={tableStyle}>
            <thead>
              <tr style={headerRowStyle}>
                <th style={thStyle}>Patient ID</th>
                <th style={thStyle}>Consent Date</th>
                <th style={thStyle}>Consent Image</th>
                <th style={thStyle}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((session) => (
                <tr key={session.id} style={rowStyle}>
                  <td style={tdStyle}>{session.id}</td>
                  <td style={tdStyle}>{new Date(session.consent_timestamp).toLocaleString()}</td>
                  <td style={tdStyle}>
                    {session.consent_scanned_url ? (
                      <img 
                        src={convertGcsToHttp(session.consent_scanned_url)} 
                        alt="Consent Snippet" 
                        style={thumbnailStyle}
                        onClick={() => window.open(convertGcsToHttp(session.consent_scanned_url), '_blank')}
                      />
                    ) : 'No Image'}
                  </td>
                  <td style={tdStyle}>
                    <button 
                      onClick={() => fetchSessionDetail(session.id)}
                      style={linkButtonStyle}
                    >
                      View Responses
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
                onSaveSuccess={() => {
                  // Optionally refresh or close modal
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
      userRole="doctor" 
      handleLogout={handleLogout} 
      maxWidth="100%" 
      padding="20px"
    >
      {content}
    </Layout>
  );
};

const contentStyle = {
  backgroundColor: '#fff',
  padding: '20px',
  borderRadius: '8px',
  boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
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
  color: '#007bff',
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
