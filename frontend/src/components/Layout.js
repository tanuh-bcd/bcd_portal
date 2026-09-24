import React from 'react';
import { LogOut } from 'lucide-react';

const Layout = ({ children, userRole, handleLogout, maxWidth = '1200px', padding = '20px', fullWidth = false }) => {
  const effectiveMaxWidth = fullWidth ? '100%' : maxWidth;
  const effectivePadding = fullWidth ? '0' : padding;
  const hospitalName = localStorage.getItem('hospitalName') || '';
  const userEmail = localStorage.getItem('userEmail') || '';
  const userName = localStorage.getItem('userName') || '';

  return (
    <div style={containerStyle}>
      <header style={headerStyle}>
        <div style={{ ...logoContainerStyle, maxWidth: effectiveMaxWidth }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'clamp(6px, 2vw, 24px)', flexWrap: 'nowrap', flexShrink: 0, minWidth: 0 }}>
            <img src="/tanuh.png" alt="TANUH Logo" style={{ height: 'clamp(24px, 7vw, 50px)', width: 'auto', objectFit: 'contain' }} />
            <img src="/MoE_Logo.svg" alt="MoE Logo" style={{ height: 'clamp(20px, 6vw, 42px)', width: 'auto', objectFit: 'contain' }} />
            <img src="/IISc_logo.png" alt="IISc Logo" style={{ height: 'clamp(26px, 7.5vw, 55px)', width: 'auto', objectFit: 'contain' }} />
          </div>
          <div style={{ textAlign: 'center', flex: '1 1 auto', minWidth: 0 }}>
            <h1 style={titleStyle}>AI enabled Breast Cancer Risk Prediction Tool</h1>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4, minWidth: 0, flexShrink: 0 }}>
            <button onClick={handleLogout} style={logoutButtonStyle}>
              <LogOut size={14} />
              Logout
            </button>
            {hospitalName && <span style={hospitalBadgeStyle}>{hospitalName} — {userRole}</span>}
            {userName && <span style={userEmailStyle}>{userName}</span>}
            {userEmail && <span style={userEmailStyle}>{userEmail}</span>}
          </div>
        </div>
      </header>

      <main style={{ ...mainStyle, maxWidth: effectiveMaxWidth, padding: effectivePadding }}>
        {children}
      </main>
    </div>
  );
};

const containerStyle = {
  display: 'flex',
  flexDirection: 'column',
  minHeight: '100vh',
  maxWidth: '100vw',
  overflowX: 'hidden', // belt-and-suspenders: the page itself never scrolls sideways
  backgroundColor: 'transparent',
  fontFamily: '"Inter", sans-serif'
};

const headerStyle = {
  padding: '14px 20px',
  backgroundColor: '#DAF3F4',
  boxShadow: '0 2px 6px rgba(0,0,0,0.06)',
  borderBottom: '1px solid rgba(0,0,0,0.08)',
};

const logoContainerStyle = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  maxWidth: '1200px',
  margin: '0 auto',
  width: '100%',
  gap: 'clamp(8px, 3vw, 20px)',
  flexWrap: 'nowrap',
};

const titleStyle = {
  fontSize: 'clamp(11px, 2.8vw, 18px)',
  fontWeight: '700',
  color: '#14868C',
  margin: 0,
  fontFamily: "'Poppins', sans-serif",
  whiteSpace: 'normal', // full title always shows -- wraps onto its own lines rather than truncating
  overflowWrap: 'break-word',
  lineHeight: 1.25,
};

const hospitalBadgeStyle = {
  display: 'inline-block',
  fontSize: 'clamp(9px, 2vw, 12px)',
  color: '#555',
  fontWeight: '500',
  whiteSpace: 'nowrap',
  maxWidth: '38vw',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
};

const logoutButtonStyle = {
  display: 'flex',
  alignItems: 'center',
  gap: '5px',
  padding: 'clamp(3px, 1vw, 5px) clamp(6px, 2vw, 12px)',
  backgroundColor: '#fff',
  color: '#dc3545',
  border: '1px solid #dc3545',
  borderRadius: '6px',
  cursor: 'pointer',
  fontWeight: '500',
  fontSize: 'clamp(10px, 2vw, 12px)',
  fontFamily: 'inherit',
  whiteSpace: 'nowrap',
};

const userEmailStyle = {
  display: 'inline-block',
  fontSize: 'clamp(8px, 1.8vw, 11px)',
  color: '#777',
  fontWeight: '400',
  whiteSpace: 'nowrap',
  maxWidth: '38vw',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
};

const mainStyle = {
  flex: 1,
  padding: '20px',
  maxWidth: '1200px',
  margin: '0 auto',
  width: '100%'
};

export default Layout;
