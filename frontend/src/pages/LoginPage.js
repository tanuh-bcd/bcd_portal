import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-toastify';
// Logos served from public/ folder for consistency with Navbar

const LoginPage = () => {
  const navigate = useNavigate();
  const [hospitals, setHospitals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loginLoading, setLoginLoading] = useState(false);
  const [error, setError] = useState(null);

  // Form state
  const [formData, setFormData] = useState({
    hospitalName: '',
    role: '',
    email: '',
    password: ''
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!formData.hospitalName || !formData.role || !formData.email || !formData.password) {
      toast.error('Please fill in all fields');
      return;
    }

    setLoginLoading(true);
    try {
      const response = await fetch(`${process.env.REACT_APP_API_URL || ''}/api/v1/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          hospital_name: formData.hospitalName,
          role: formData.role.charAt(0).toUpperCase() + formData.role.slice(1), // Capitalize first letter to match backend expected roles (Admin, Doctor, Staff)
          email: formData.email,
          password: formData.password
        }),
      });

      const data = await response.json();

      if (response.ok) {
        const userName = data.full_name || formData.email;
        toast.success(`\u{1F44B} Welcome, ${userName}!`, { autoClose: 4000 });
        localStorage.setItem('token', data.access_token);
        localStorage.setItem('role', formData.role);
        localStorage.setItem('hospitalName', formData.hospitalName);
        localStorage.setItem('userEmail', formData.email);
        localStorage.setItem('userName', userName);
        
        const roleLower = formData.role.toLowerCase();
        if (roleLower === 'admin') {
          navigate('/admin');
        } else if (roleLower === 'clinician') {
          navigate('/doctor');
        } else if (roleLower === 'staff') {
          navigate('/patient');
        } else {
          // Handle other roles when their pages are ready
          // navigate('/dashboard');
        }
      } else {
        // Handle specific error messages from backend if needed
        const errorMsg = data.detail || 'Credentials wrong';
        toast.error(errorMsg);
      }
    } catch (err) {
      console.error('Login error:', err);
      toast.error('An error occurred during login. Please try again.');
    } finally {
      setLoginLoading(false);
    }
  };

  useEffect(() => {
    const fetchHospitals = async () => {
      try {
        const response = await fetch(`${process.env.REACT_APP_API_URL || ''}/api/v1/auth/hospitals`);
        if (!response.ok) {
          throw new Error('Failed to fetch hospitals');
        }
        const data = await response.json();
        setHospitals(data);
      } catch (err) {
        console.error('Error fetching hospitals:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchHospitals();
  }, []);

  return (
    <div style={{ 
      display: 'flex', 
      flexDirection: 'column', 
      minHeight: '100vh', 
      padding: '20px',
      backgroundColor: 'transparent',
      fontFamily: '"Inter", sans-serif'
    }}>
      <header style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        marginBottom: '30px',
        gap: '16px'
      }}>
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '2.5rem', flexWrap: 'wrap' }}>
          <a href={process.env.REACT_APP_WEBSITE_URL} target="_blank" rel="noopener noreferrer">
            <img src="/tanuh.png" alt="TANUH Logo" style={{ height: '65px', objectFit: 'contain' }} />
          </a>
          <img src="/MoE_Logo.svg" alt="Ministry of Education Logo" style={{ height: '55px', objectFit: 'contain' }} />
          <img src="/IISc_logo.png" alt="IISc Logo" style={{ height: '75px', objectFit: 'contain' }} />
        </div>
        <h1 style={{
          fontSize: '22px',
          fontWeight: '700',
          color: '#14868C',
          textAlign: 'center',
          margin: 0,
          fontFamily: "'Poppins', sans-serif"
        }}>
          AI enabled Breast Cancer Risk Prediction Tool
        </h1>
        <p style={{ color: '#e91e8c', fontWeight: 800, fontSize: '1.5rem', fontFamily: "'Poppins', sans-serif", letterSpacing: '1px', textTransform: 'uppercase', margin: 0 }}>
          PinkShieldAI
        </p>
      </header>

      <main style={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', padding: '0 16px' }}>
        <div style={{ width: '100%', maxWidth: '420px', border: '1px solid rgba(0,0,0,0.05)', padding: '30px', borderRadius: '16px', boxShadow: '0 8px 30px rgba(20,134,140,0.1)', backgroundColor: 'white', borderTop: '5px solid #14868C' }}>
          <h2 style={{ textAlign: 'center', marginBottom: '24px' }}>Enter credentials</h2>
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label htmlFor="hospitalName">Hospital Name</label>
              <select 
                id="hospitalName" 
                name="hospitalName" 
                value={formData.hospitalName}
                onChange={handleChange}
                style={{ padding: '8px', borderRadius: '4px', border: '1px solid #ccc' }}
                disabled={loading}
              >
                <option value="">{loading ? 'Loading hospitals...' : 'Select Hospital'}</option>
                {hospitals.map((hospital) => (
                  <option key={hospital.id} value={hospital.name}>
                    {hospital.name}
                  </option>
                ))}
              </select>
              {error && <span style={{ color: 'red', fontSize: '12px' }}>{error}</span>}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label htmlFor="role">Role</label>
              <select 
                id="role" 
                name="role" 
                value={formData.role}
                onChange={handleChange}
                style={{ padding: '8px', borderRadius: '4px', border: '1px solid #ccc' }}
              >
                <option value="">Select Role</option>
                <option value="clinician">Clinician</option>
                <option value="admin">Admin</option>
                <option value="staff">Staff</option>
              </select>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label htmlFor="email">Email address</label>
              <input 
                type="email" 
                id="email" 
                name="email" 
                value={formData.email}
                onChange={handleChange}
                style={{ padding: '8px', borderRadius: '4px', border: '1px solid #ccc' }} 
              />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label htmlFor="password">Password</label>
              <input 
                type="password" 
                id="password" 
                name="password" 
                value={formData.password}
                onChange={handleChange}
                style={{ padding: '8px', borderRadius: '4px', border: '1px solid #ccc' }} 
              />
            </div>
            <button 
              type="submit" 
              disabled={loginLoading}
              style={{ 
                padding: '10px', 
                backgroundColor: loginLoading ? '#ccc' : '#14868C', 
                color: 'white', 
                border: 'none', 
                borderRadius: '4px', 
                cursor: loginLoading ? 'not-allowed' : 'pointer', 
                marginTop: '10px' 
              }}
            >
              {loginLoading ? 'Logging in...' : 'Login'}
            </button>
          </form>
          <div style={{ marginTop: '16px', textAlign: 'center' }}>
            <button onClick={() => navigate('/reset-password')} style={{ background: 'none', border: 'none', color: '#14868C', cursor: 'pointer', textDecoration: 'underline' }}>
              Reset password
            </button>
          </div>
        </div>
      </main>
    </div>
  );
};

export default LoginPage;
