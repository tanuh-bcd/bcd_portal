// // src/components/Consent.jsx
// import React, { useState } from 'react';
// import './Consent.css';

// function Consent({ onAccept }) {
//   const [isChecked, setIsChecked] = useState(false);

//   return (
//     <div className="consent-container">
//       <h2>Consent</h2>
//       <p>By participating in this survey, you agree to provide your information for the purpose of this research. Your participation is completely voluntary.</p>

//       <h3>Purpose</h3>
//       <p>The information you provide will be used for research to better understand the risk factors for breast cancer in the Indian population. Our goal is to create a model that can help individuals assess their personal risk and empower them to make informed health decisions. The model will calculate a 5-year and lifetime breast cancer risk score for each participant. This study is for research purposes only, and the information will not be used to provide a medical diagnosis or treatment plan.</p>

//       <h3>Security</h3>
//       <p>All data you submit will be stored securely. No personally identifiable information are collected. The data will be de-identified and analyzed in an aggregated format, so it will be impossible to link your responses back to you.</p>
      
//       <h3>Transparency (Data Usage)</h3>
//       <p>The data collected will be used exclusively for academic research related to breast cancer risk factors and assessment. It may be shared with other researchers and collaborators for the same purpose, but it will always be in a de-identified and aggregated format. The results of this study may be published in scientific journals or presented at conferences.</p>

//       <div className="consent-checkbox">
//         <input
//           type="checkbox"
//           id="consent-check"
//           checked={isChecked}
//           onChange={() => setIsChecked(!isChecked)}
//         />
//         <label htmlFor="consent-check">I agree to the above consent statement</label>
//       </div>

//       <button onClick={onAccept} disabled={!isChecked}>
//         Accept & Continue
//       </button>
//     </div>
//   );
// }

// export default Consent;


// final updated one


// import React, { useState } from 'react';
// import './Consent.css';
// import consentData from '../../public/locales/english/consent.json' with { type: 'json' };

// function Consent({ onAccept }) {
//   const [isChecked, setIsChecked] = useState(false);

//   return (
//     <div className="consent-container">

//       <img src="/tanuh.png" alt={consentData.logos.tanuhAlt} className="logo tanuh-logo" />
//       <img src="/IISc_logo.png" alt={consentData.logos.iiscAlt} className="logo iisc-logo" />

//       <h2>{consentData.title}</h2>

//       <div className="consent-header">
//         <p><strong>Study Title:</strong> {consentData.header.studyTitle}</p>
//         <p><strong>Sponsor/Institution:</strong> {consentData.header.sponsor}</p>
//         <p><strong>Program Manager:</strong> {consentData.header.programManager}</p>
//         <p><strong>IEC Approval No.:</strong> {consentData.header.iecApproval}</p>
//       </div>

//       {consentData.sections.map((section, idx) => (
//         <div key={idx} className={section.className ? section.className : 'consent-section'}>
//           <h3>{section.heading}</h3>
//           {section.paragraphs.map((para, pIdx) => (
//             <p key={pIdx} className={para.className || undefined}>
//               {para.strong && <strong>{para.strong} </strong>}
//               {para.text}
//             </p>
//           ))}
//         </div>
//       ))}

//       <div className="consent-checkbox">
//         <input
//           type="checkbox"
//           id="consent-check"
//           checked={isChecked}
//           onChange={() => setIsChecked(!isChecked)}
//         />
//         <label htmlFor="consent-check">{consentData.checkboxLabel}</label>
//       </div>

//       <button onClick={onAccept} disabled={!isChecked}>
//         {consentData.buttonText}
//       </button>
//     </div>
//   );
// }

// export default Consent;


import React, { useEffect, useState, useRef } from 'react';
import './Consent.css';
import { useTranslation } from 'react-i18next';
import { Camera, Upload, X, RefreshCw } from 'lucide-react';
import LanguageSwitcher from './LanguageSwitcher';

function Consent({ onAccept }) {
  const [isChecked, setIsChecked] = useState(false);
  const [scannedFile, setScannedFile] = useState(null);
  const [isCameraActive, setIsCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState(null);
  const [facingMode, setFacingMode] = useState('environment');
  const { t, i18n } = useTranslation('consent');
  const [databaseContent, setDatabaseContent] = useState(null);

  useEffect(() => {
    const languageCodes = {
      english: 'en', hindi: 'hi', bengali: 'bn', gujarati: 'gu', kannada: 'kn',
      malayalam: 'ml', marathi: 'mr', odia: 'or', punjabi: 'pa', tamil: 'ta', telugu: 'te',
      en: 'en', hi: 'hi', bn: 'bn', gu: 'gu', kn: 'kn', ml: 'ml', mr: 'mr',
      or: 'or', pa: 'pa', ta: 'ta', te: 'te',
    };
    const languageCode = languageCodes[i18n.resolvedLanguage || i18n.language] || 'en';
    const apiUrl = process.env.REACT_APP_API_URL || '';
    let cancelled = false;
    const query = new URLSearchParams({ lang: languageCode });
    const questionnaireVersion = process.env.REACT_APP_QUESTIONNAIRE_VERSION;
    if (questionnaireVersion) query.set('version', questionnaireVersion);

    fetch(`${apiUrl}/api/participant-information?${query.toString()}`)
      .then(response => {
        if (!response.ok) throw new Error('Participant information unavailable');
        return response.json();
      })
      .then(content => { if (!cancelled) setDatabaseContent(content); })
      .catch(() => { if (!cancelled) setDatabaseContent(null); });
    return () => { cancelled = true; };
  }, [i18n.language, i18n.resolvedLanguage]);

  const content = databaseContent || {
    title: t('title'),
    headernames: t('headernames', { returnObjects: true }),
    header: t('header', { returnObjects: true }),
    sections: t('sections', { returnObjects: true }),
    checkboxLabel: t('checkboxLabel'),
    buttonText: t('buttonText'),
  };

  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);

  const startCamera = async (mode = facingMode) => {
    setCameraError(null);
    stopCamera();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: mode } });
      streamRef.current = stream;
      setIsCameraActive(true);
      setTimeout(() => {
        if (videoRef.current && streamRef.current) {
          videoRef.current.srcObject = streamRef.current;
          videoRef.current.play().catch(() => {});
        }
      }, 100);
    } catch (err) {
      setCameraError('Could not access camera. Please use the upload option.');
    }
  };

  const stopCamera = () => {
    if (streamRef.current) { streamRef.current.getTracks().forEach(track => track.stop()); streamRef.current = null; }
    if (videoRef.current) videoRef.current.srcObject = null;
    setIsCameraActive(false);
  };

  const capturePhoto = () => {
    if (!videoRef.current || !canvasRef.current) return;
    const video = videoRef.current;
    const canvas = canvasRef.current;

    const doCapture = () => {
      if (video.videoWidth === 0 || video.videoHeight === 0) {
        setCameraError('Camera not ready. Please wait a moment and try again.');
        return;
      }
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);

      try {
        canvas.toBlob((blob) => {
          if (blob) {
            setScannedFile(new File([blob], `consent-${Date.now()}.jpg`, { type: 'image/jpeg' }));
            setTimeout(() => stopCamera(), 100);
          } else {
            const dataUrl = canvas.toDataURL('image/jpeg', 0.9);
            const arr = dataUrl.split(',');
            const bstr = atob(arr[1]);
            const u8 = new Uint8Array(bstr.length);
            for (let i = 0; i < bstr.length; i++) u8[i] = bstr.charCodeAt(i);
            setScannedFile(new File([u8], `consent-${Date.now()}.jpg`, { type: 'image/jpeg' }));
            setTimeout(() => stopCamera(), 100);
          }
        }, 'image/jpeg', 0.9);
      } catch (e) {
        setCameraError('Capture failed. Please try again or use upload.');
      }
    };

    if (video.videoWidth === 0) {
      setTimeout(doCapture, 500);
    } else {
      doCapture();
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) setScannedFile(e.target.files[0]);
  };

  const handleAccept = () => {
    onAccept({ file: scannedFile || null });
  };

  return (
    <div className="consent-container">
      <div className="logos-container" style={{ marginBottom: '1.5rem' }}>
        <img src="/tanuh.png" alt="TANUH Logo" className="logo-tanuh" />
        <img src="/MoE_Logo.svg" alt="MoE Logo" className="logo-moe" />
        <img src="/IISc_logo.png" alt="IISc Logo" className="logo-iisc" />
      </div>
      <LanguageSwitcher />

      {/* Use the 't' function to get the text */}
      <h2>{content.title}</h2>

      <div className="consent-header">
        <p><strong>{content.headernames.studyTitle} :</strong> {content.header.studyTitle}</p>
        <p><strong>{content.headernames.sponsor} :</strong> {content.header.sponsor}</p>
        <p><strong>{content.headernames.iecApproval} :</strong> {content.header.iecApproval}</p>
      </div>

      {/* Loop through sections from the JSON file */}
      {/* {returnObjects: true} is important for looping */}
      {(content.sections || []).map((section, idx) => (
        <div key={idx} className={section.className ? section.className : 'consent-section'}>
          <h3>{section.heading}</h3>
          {section.paragraphs.map((para, pIdx) => (
            <p key={pIdx} className={para.className || undefined}>
              {para.strong && <strong>{para.strong} </strong>}
              {para.text}
            </p>
          ))}
        </div>
      ))}

      <div className="consent-upload">
        <strong className="consent-upload-title">Consent Upload</strong>

        {!isCameraActive && !scannedFile && (
          <div className="upload-options">
            <button type="button" className="action-button camera-btn" onClick={() => startCamera()}>
              <Camera size={20} />
              Take Photo
            </button>
            <button type="button" className="action-button upload-btn" onClick={() => document.getElementById('consent-file-jsx').click()}>
              <Upload size={20} />
              Upload Image
            </button>
            <input type="file" id="consent-file-jsx" accept="image/*,application/pdf" onChange={handleFileChange} style={{ display: 'none' }} />
          </div>
        )}

        {isCameraActive && (
          <div className="camera-preview-container">
            <video ref={videoRef} autoPlay playsInline muted className="camera-video" />
            <div className="camera-controls">
              <button type="button" className="action-button capture-btn" onClick={capturePhoto}>
                <div className="capture-inner" />
              </button>
              <button type="button" className="action-button close-btn" onClick={stopCamera}>
                <X size={24} />
              </button>
            </div>
            <canvas ref={canvasRef} style={{ display: 'none' }} />
          </div>
        )}

        {cameraError && <p className="camera-error">{cameraError}</p>}

        {scannedFile && (
          <div style={{ textAlign: 'center', marginTop: 12 }}>
            <img
              src={URL.createObjectURL(scannedFile)}
              alt="Captured consent"
              style={{ maxWidth: '100%', maxHeight: 250, borderRadius: 10, border: '2px solid #14868C', marginBottom: 10 }}
            />
            <div className="selected-file-container">
              <p className="file-name">{scannedFile.name}</p>
              <button type="button" className="action-button retake-btn" onClick={() => { setScannedFile(null); startCamera(); }}>
                <RefreshCw size={16} /> Retake
              </button>
              <button type="button" className="action-button remove-file-btn" onClick={() => setScannedFile(null)}>
                <X size={16} />
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="consent-checkbox">
        <input
          type="checkbox"
          id="consent-check"
          checked={isChecked}
          onChange={() => setIsChecked(!isChecked)}
        />
        <label htmlFor="consent-check">{content.checkboxLabel}</label>
      </div>

      <button onClick={handleAccept} disabled={!isChecked}>
        {content.buttonText}
      </button>
    </div>
  );
}

export default Consent;
