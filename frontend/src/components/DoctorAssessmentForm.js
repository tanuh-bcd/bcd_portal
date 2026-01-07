import React, { useState } from 'react';

const DoctorAssessmentForm = ({ sessionId, onSaveSuccess }) => {
  const [formData, setFormData] = useState({
    questionnaire_feedback: '',
    is_questionnaire_correct: false,
    mammo_birads: '',
    mammo_density: '',
    us_biopsy_birads: '',
    us_biopsy_density: '',
    precision_diagnosis: '',
    datapoint_feedback: ''
  });

  const [files, setFiles] = useState({
    mammo_dicom: [],
    mammo_reading: null,
    us_video: null,
    us_reading: null,
    biopsy_doc: null
  });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });

  const handleInputChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const handleFileChange = (e) => {
    const { name, files: selectedFiles } = e.target;
    if (name === 'mammo_dicom') {
      // Limit to 10 files
      const fileList = Array.from(selectedFiles).slice(0, 10);
      setFiles(prev => ({ ...prev, [name]: fileList }));
    } else {
      setFiles(prev => ({ ...prev, [name]: selectedFiles[0] }));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setMessage({ type: '', text: '' });

    const submitData = new FormData();
    submitData.append('patient_session_id', sessionId);
    submitData.append('questionnaire_feedback', formData.questionnaire_feedback);
    submitData.append('is_questionnaire_correct', formData.is_questionnaire_correct);
    submitData.append('mammo_birads', formData.mammo_birads);
    submitData.append('mammo_density', formData.mammo_density);
    submitData.append('us_biopsy_birads', formData.us_biopsy_birads);
    submitData.append('us_biopsy_density', formData.us_biopsy_density);
    submitData.append('precision_diagnosis', formData.precision_diagnosis);
    submitData.append('datapoint_feedback', formData.datapoint_feedback);

    // Append files
    files.mammo_dicom.forEach(file => {
      submitData.append('mammo_dicom', file);
    });
    if (files.mammo_reading) submitData.append('mammo_reading', files.mammo_reading);
    if (files.us_video) submitData.append('us_video', files.us_video);
    if (files.us_reading) submitData.append('us_reading', files.us_reading);
    if (files.biopsy_doc) submitData.append('biopsy_doc', files.biopsy_doc);

    try {
      const token = localStorage.getItem('token');
      const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/v1/patient/assessment`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: submitData
      });

      if (response.ok) {
        setMessage({ type: 'success', text: 'Assessment saved successfully!' });
        if (onSaveSuccess) onSaveSuccess();
      } else {
        const errorData = await response.json();
        setMessage({ type: 'error', text: `Failed to save assessment: ${errorData.detail || 'Unknown error'}` });
      }
    } catch (err) {
      console.error(err);
      setMessage({ type: 'error', text: 'An error occurred while saving the assessment.' });
    } finally {
      setIsSubmitting(false);
    }
  };

  const formStyle = {
    marginTop: '20px',
    padding: '20px',
    border: '1px solid #ddd',
    borderRadius: '8px',
    backgroundColor: '#f9f9f9'
  };

  const sectionStyle = {
    marginBottom: '20px',
    paddingBottom: '15px',
    borderBottom: '1px solid #eee'
  };

  const labelStyle = {
    display: 'block',
    marginBottom: '5px',
    fontWeight: 'bold',
    color: '#555'
  };

  const inputStyle = {
    width: '100%',
    padding: '8px',
    marginBottom: '10px',
    borderRadius: '4px',
    border: '1px solid #ccc',
    boxSizing: 'border-box'
  };

  const selectStyle = {
    width: '100%',
    padding: '8px',
    marginBottom: '10px',
    borderRadius: '4px',
    border: '1px solid #ccc',
    backgroundColor: 'white'
  };

  const checkboxContainerStyle = {
    display: 'flex',
    alignItems: 'center',
    marginBottom: '15px'
  };

  const submitButtonStyle = {
    backgroundColor: '#007bff',
    color: 'white',
    padding: '10px 20px',
    border: 'none',
    borderRadius: '4px',
    cursor: isSubmitting ? 'not-allowed' : 'pointer',
    fontSize: '16px',
    fontWeight: 'bold',
    width: '100%'
  };

  const biradsOptions = ['0', '1', '2', '3', '4', '5', '6'];
  const densityOptions = ['A', 'B', 'C', 'D'];

  return (
    <div style={formStyle}>
      <h3 style={{ marginBottom: '15px', color: '#333' }}>Doctor Clinical Assessment</h3>
      <form onSubmit={handleSubmit}>
        <div style={sectionStyle}>
          <label style={labelStyle}>Questionnaire Feedback</label>
          <textarea
            name="questionnaire_feedback"
            value={formData.questionnaire_feedback}
            onChange={handleInputChange}
            style={{ ...inputStyle, height: '80px', resize: 'vertical' }}
            placeholder="Enter feedback regarding the questionnaire..."
          />
          <div style={checkboxContainerStyle}>
            <input
              type="checkbox"
              id="is_questionnaire_correct"
              name="is_questionnaire_correct"
              checked={formData.is_questionnaire_correct}
              onChange={handleInputChange}
              style={{ marginRight: '10px' }}
            />
            <label htmlFor="is_questionnaire_correct">Questionnaire is correct</label>
          </div>
        </div>

        <div style={sectionStyle}>
          <h4 style={{ marginBottom: '10px' }}>Mammography</h4>
          <label style={labelStyle}>Upload DICOM Images (up to 10)</label>
          <input
            type="file"
            name="mammo_dicom"
            multiple
            accept=".dcm,application/dicom"
            onChange={handleFileChange}
            style={inputStyle}
          />
          
          <label style={labelStyle}>Mammography Reading (Image or PDF)</label>
          <input
            type="file"
            name="mammo_reading"
            accept="image/*,.pdf"
            onChange={handleFileChange}
            style={inputStyle}
          />

          <div style={{ display: 'flex', gap: '15px' }}>
            <div style={{ flex: 1 }}>
              <label style={labelStyle}>BIRADS Category</label>
              <select
                name="mammo_birads"
                value={formData.mammo_birads}
                onChange={handleInputChange}
                style={selectStyle}
              >
                <option value="">Select BIRADS</option>
                {biradsOptions.map(opt => <option key={opt} value={opt}>{opt}</option>)}
              </select>
            </div>
            <div style={{ flex: 1 }}>
              <label style={labelStyle}>Breast Density</label>
              <select
                name="mammo_density"
                value={formData.mammo_density}
                onChange={handleInputChange}
                style={selectStyle}
              >
                <option value="">Select Density</option>
                {densityOptions.map(opt => <option key={opt} value={opt}>{opt}</option>)}
              </select>
            </div>
          </div>
        </div>

        <div style={sectionStyle}>
          <h4 style={{ marginBottom: '10px' }}>Ultrasound & Biopsy</h4>
          <label style={labelStyle}>Ultrasound Video</label>
          <input
            type="file"
            name="us_video"
            accept="video/*"
            onChange={handleFileChange}
            style={inputStyle}
          />

          <label style={labelStyle}>Ultrasound Reading (Image or PDF)</label>
          <input
            type="file"
            name="us_reading"
            accept="image/*,.pdf"
            onChange={handleFileChange}
            style={inputStyle}
          />

          <label style={labelStyle}>Biopsy Document (Image or PDF)</label>
          <input
            type="file"
            name="biopsy_doc"
            accept="image/*,.pdf"
            onChange={handleFileChange}
            style={inputStyle}
          />

          <div style={{ display: 'flex', gap: '15px' }}>
            <div style={{ flex: 1 }}>
              <label style={labelStyle}>US/Biopsy BIRADS</label>
              <select
                name="us_biopsy_birads"
                value={formData.us_biopsy_birads}
                onChange={handleInputChange}
                style={selectStyle}
              >
                <option value="">Select BIRADS</option>
                {biradsOptions.map(opt => <option key={opt} value={opt}>{opt}</option>)}
              </select>
            </div>
            <div style={{ flex: 1 }}>
              <label style={labelStyle}>US/Biopsy Density</label>
              <select
                name="us_biopsy_density"
                value={formData.us_biopsy_density}
                onChange={handleInputChange}
                style={selectStyle}
              >
                <option value="">Select Density</option>
                {densityOptions.map(opt => <option key={opt} value={opt}>{opt}</option>)}
              </select>
            </div>
          </div>
        </div>

        <div style={sectionStyle}>
          <h4 style={{ marginBottom: '10px' }}>Final Assessment</h4>
          <label style={labelStyle}>Precision Diagnosis</label>
          <select
            name="precision_diagnosis"
            value={formData.precision_diagnosis}
            onChange={handleInputChange}
            style={selectStyle}
          >
            <option value="">Select Diagnosis</option>
            <option value="4A">4A</option>
            <option value="4B">4B</option>
            <option value="4C">4C</option>
          </select>

          <label style={labelStyle}>Datapoint Feedback</label>
          <textarea
            name="datapoint_feedback"
            value={formData.datapoint_feedback}
            onChange={handleInputChange}
            style={{ ...inputStyle, height: '80px', resize: 'vertical' }}
            placeholder="Additional datapoint feedback..."
          />
        </div>

        {message.text && (
          <div style={{
            padding: '10px',
            marginBottom: '15px',
            borderRadius: '4px',
            backgroundColor: message.type === 'success' ? '#d4edda' : '#f8d7da',
            color: message.type === 'success' ? '#155724' : '#721c24',
            border: `1px solid ${message.type === 'success' ? '#c3e6cb' : '#f5c6cb'}`
          }}>
            {message.text}
          </div>
        )}

        <button
          type="submit"
          disabled={isSubmitting}
          style={submitButtonStyle}
        >
          {isSubmitting ? 'Saving...' : 'Save Assessment'}
        </button>
      </form>
    </div>
  );
};

export default DoctorAssessmentForm;
