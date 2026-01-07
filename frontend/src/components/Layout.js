import React from 'react';
import tanuhLogo from '../assets/tanuh.png';
import iiscLogo from '../assets/IISc_logo.png';

const Layout = ({ children, userRole, handleLogout, maxWidth = '1200px', padding = '20px' }) => {
  return (
    <div style={containerStyle}>
      <header style={headerStyle}>
        <div style={{
          ...logoContainerStyle,
          maxWidth: maxWidth
        }}>
          <img src={tanuhLogo} alt="Tanuh Logo" style={logoStyle} />
          <h1 style={titleStyle}>AI enabled Breast Cancer Screening Tool</h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
            <button 
              onClick={handleLogout}
              style={{
                padding: '8px 16px',
                backgroundColor: '#f8d7da',
                color: '#721c24',
                border: '1px solid #f5c6cb',
                borderRadius: '4px',
                cursor: 'pointer'
              }}
            >
              Logout
            </button>
            <img src={iiscLogo} alt="IISc Logo" style={logoStyle} />
          </div>
        </div>
      </header>

      <main style={{
        ...mainStyle,
        maxWidth: maxWidth,
        padding: padding
      }}>
        {children}
      </main>
    </div>
  );
};

const containerStyle = {
  display: 'flex',
  flexDirection: 'column',
  minHeight: '100vh',
  backgroundColor: '#fff5f7',
  fontFamily: '"Inter", sans-serif'
};

const headerStyle = {
  padding: '20px',
  backgroundColor: 'white',
  boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
};

const logoContainerStyle = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  maxWidth: '1200px',
  margin: '0 auto',
  width: '100%',
  gap: '20px'
};

const logoStyle = {
  height: '64px',
  width: '64px',
  objectFit: 'contain'
};

const titleStyle = {
  fontSize: '20px',
  fontWeight: '600',
  color: '#8B008B',
  textAlign: 'center',
  flex: '1'
};

const mainStyle = {
  flex: 1,
  padding: '20px',
  maxWidth: '1200px',
  margin: '0 auto',
  width: '100%'
};

export default Layout;
