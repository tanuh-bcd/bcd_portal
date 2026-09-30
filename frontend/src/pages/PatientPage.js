import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import PublicQuestionnairePage from './PublicQuestionnairePage';

const PatientPage = ({ isEmbedded = false }) => {
  const navigate = useNavigate();
  const hospitalName = localStorage.getItem('hospitalName') || '';

  useEffect(() => {
    if (isEmbedded) return;
    const role = localStorage.getItem('role')?.toLowerCase();
    const token = localStorage.getItem('token');
    if (!token || (role !== 'staff' && role !== 'admin')) {
      navigate('/login');
    }
  }, [navigate, isEmbedded]);

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    localStorage.removeItem('hospitalName');
    localStorage.removeItem('userEmail');
    localStorage.removeItem('userName');
    navigate('/login');
  };

  const content = (
    <div style={contentStyle}>
      <PublicQuestionnairePage lockedHospitalName={hospitalName} />
    </div>
  );

  if (isEmbedded) {
    return content;
  }

  return (
    <Layout userRole="staff" handleLogout={handleLogout} fullWidth={true}>
      {content}
    </Layout>
  );
};

const contentStyle = {
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'flex-start',
  padding: '20px 16px',
  minHeight: '400px',
  color: '#666',
  width: '100%',
};

export default PatientPage;
