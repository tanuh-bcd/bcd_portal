import React, { useState, useEffect, useRef } from 'react';
import './Demo.css';
import { useTranslation } from 'react-i18next';
import { CheckCircle, Info } from 'lucide-react';
import RiskTable from './RiskTable';

const API_URL = process.env.REACT_APP_API_URL || '';

const buildDemoForm = (rows) => {
  const questions = {};
  const nodes = new Map();
  rows.forEach(row => {
    questions[row.question_key] = {
      question: row.question_text,
      answers: (row.options || []).map(option => option.option_label),
    };
    nodes.set(row.id, {
      key: row.question_key,
      type: row.input_type || (row.response_type === 'numbers_only' ? 'number' : 'text'),
      min: row.min_value,
      max: row.max_value,
      parentId: row.parent_question_id,
      triggerAnswer: row.trigger_answer,
      section: row.section || 'Questionnaire',
      subQuestions: [],
    });
  });
  const sections = new Map();
  rows.forEach(row => {
    const node = nodes.get(row.id);
    if (node.parentId && nodes.has(node.parentId)) {
      const parent = nodes.get(node.parentId);
      if (node.triggerAnswer) node.condition = { key: parent.key, value: node.triggerAnswer };
      parent.subQuestions.push(node);
    } else {
      if (!sections.has(node.section)) sections.set(node.section, []);
      sections.get(node.section).push(node);
    }
  });
  return { formStructure: Array.from(sections, ([title, sectionQuestions]) => ({ title, questions: sectionQuestions })), questions };
};

const sampleAnswer = (node, questions) => {
  const answers = questions[node.key]?.answers || [];
  if (answers.length) return answers[0];
  if (node.type === 'number' || node.type === 'number_or_unknown') {
    const min = Number(node.min);
    const max = Number(node.max);
    return String(Number.isFinite(min) && Number.isFinite(max) ? Math.min(max, Math.max(min, 35)) : 35);
  }
  if (node.key === 'V2_Q01') return 'DEMO-001';
  if (node.key === 'V2_Q02') return 'Demo Institution';
  return 'Sample response';
};

const Demo = () => {
  const { t, ready } = useTranslation(['consent', 'questionnaire', 'thankyou', 'demo']);
  const { t: tThankYou } = useTranslation('thankyou');
  const [currentStep, setCurrentStep] = useState(0);
  const [demoPhase, setDemoPhase] = useState('init');
  const [consentChecked, setConsentChecked] = useState(false);
  const [langSelected, setLangSelected] = useState('');
  const [activeHighlight, setActiveHighlight] = useState(null);
  const [focusedQuestion, setFocusedQuestion] = useState(null);
  const [typedValues, setTypedValues] = useState({});
  const [isAutoPlaying, setIsAutoPlaying] = useState(true);
  const [simulationKey, setSimulationKey] = useState(0);
  const [demoContent, setDemoContent] = useState(null);
  const [demoForm, setDemoForm] = useState(null);
  const [demoError, setDemoError] = useState('');
  const [databaseConsent, setDatabaseConsent] = useState(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    fetch('/locales/english/demo_content.json')
      .then(r => r.json())
      .then(setDemoContent)
      .catch(() => setDemoContent({ golden_path: {}, walkthrough: {} }));
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_URL}/api/v1/patient/questions?lang=en&version=2`)
      .then(response => {
        if (!response.ok) throw new Error(`Questionnaire request failed (${response.status})`);
        return response.json();
      })
      .catch(() => fetch('/demo_questionnaire_v2.json').then(response => {
        if (!response.ok) throw new Error('Version 2 preview data is unavailable');
        return response.json();
      }))
      .then(rows => {
        if (!Array.isArray(rows) || !rows.some(row => row.question_key?.startsWith('V2_'))) {
          throw new Error('Version 2 questionnaire is unavailable');
        }
        if (!cancelled) setDemoForm(buildDemoForm(rows));
      })
      .catch(error => { if (!cancelled) setDemoError(error.message); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_URL}/api/participant-information?lang=en&version=2`)
      .then(response => {
        if (!response.ok) throw new Error('Participant information unavailable');
        return response.json();
      })
      .catch(() => fetch('/demo_consent_v2.json').then(response => response.json()))
      .then(content => { if (!cancelled) setDatabaseConsent(content); })
      .catch(error => { if (!cancelled) setDemoError(error.message); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (demoPhase === 'simulating' && focusedQuestion) {
      const el = document.querySelector('.demo-question.focused');
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [focusedQuestion, demoPhase]);

  const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

  const getRiskLevel = (score, tFunc) => {
    const rows = tFunc('interpretation.data', { returnObjects: true });
    const levels = Array.isArray(rows) ? rows.map(r => r.level) : ["Baseline Risk", "Evident Risk", "Significant Risk", "High Risk"];
    const numScore = parseFloat(score);
    if (isNaN(numScore)) return null;
    if (numScore < 0.4004) return levels[0];
    if (numScore >= 0.4004 && numScore < 0.574) return levels[1];
    if (numScore >= 0.574 && numScore < 0.795) return levels[2];
    if (numScore >= 0.795) return levels[3];
    return null;
  };

  const highlights = demoContent?.walkthrough || {};
  const mockRiskResult = 82;
  const score = ready ? (mockRiskResult / 100).toFixed(2) : '0';
  const userRiskLevel = ready ? getRiskLevel(score, tThankYou) : null;
  const thankYouData = ready ? t('thankyou:interpretation.data', { returnObjects: true }) : [];
  const highlightedRow = Array.isArray(thankYouData) ? thankYouData.find(row => row.level === userRiskLevel) : null;

  const formStructure = demoForm?.formStructure || [];
  const questionsDict = demoForm?.questions || {};
  const consentData = databaseConsent || (ready ? {
    title: t('consent:title'),
    header: t('consent:header', { returnObjects: true }),
    headernames: t('consent:headernames', { returnObjects: true }),
    sections: t('consent:sections', { returnObjects: true }),
    checkboxLabel: t('consent:checkboxLabel'),
    buttonText: t('consent:buttonText')
  } : {});

  const totalSteps = (Array.isArray(formStructure) ? formStructure.length : 0) + 2;

  const typeValue = async (key, value, isMounted) => {
    if (!isMounted()) return;
    if (typeof value !== 'string' || !value) {
      setTypedValues(prev => ({...prev, [key]: value}));
      return;
    }
    let current = '';
    for (let i = 0; i < value.length; i++) {
      if (!isMounted()) return;
      current += value[i];
      setTypedValues(prev => ({...prev, [key]: current}));
      await sleep(40);
    }
  };

  useEffect(() => {
    if (!ready || !demoContent || !demoForm || !databaseConsent) return;

    let isMounted = true;
    const checkMounted = () => isMounted;

    const runSimulation = async () => {
      setDemoPhase('init');
      setCurrentStep(0);
      setFocusedQuestion('consent-section');
      setActiveHighlight(highlights.consent);
      if (!checkMounted()) return;
      await sleep(1500);

      setFocusedQuestion('lang_support');
      setActiveHighlight(highlights.lang_support);
      setDemoPhase('lang-dropdown-open');
      await sleep(1500);
      setLangSelected('English');
      setDemoPhase('lang-selected');
      await sleep(1500);
      setFocusedQuestion('consent-section');
      setActiveHighlight(highlights.consent);

      setDemoPhase('consent-scrolling');
      const el = scrollRef.current;
      if (el) {
        const distance = el.scrollHeight - el.clientHeight;
        const scrollSteps = 60;
        const stepMs = 8000 / scrollSteps;
        const stepAmt = distance / scrollSteps;
        for (let i = 0; i < scrollSteps; i++) {
          if (!checkMounted()) return;
          el.scrollTop += stepAmt;
          await sleep(stepMs);
        }
      }
      await sleep(500);

      setDemoPhase('checkbox-blinking');
      await sleep(800);
      setConsentChecked(true);
      setDemoPhase('button-blinking');
      await sleep(1200);

      setDemoPhase('simulating');

      const getVisibleQuestions = () => {
        const visible = [];
        const traverse = (questions) => {
          questions.forEach(q => {
            if (q.condition) {
              const parent = visible.find(item => item.key === q.condition.key);
              const parentVal = parent ? sampleAnswer(parent, questionsDict) : undefined;
              if (parentVal !== q.condition.value) return;
            }
            visible.push(q);
            if (q.subQuestions) traverse(q.subQuestions);
          });
        };
        if (Array.isArray(formStructure)) {
          formStructure.forEach(section => traverse(section.questions));
        }
        return visible;
      };

      const visibleQueue = getVisibleQuestions();
      for (let i = 0; i < visibleQueue.length; i++) {
        if (!checkMounted()) return;
        const qNode = visibleQueue[i];
        const qKey = qNode.key;
        const targetVal = sampleAnswer(qNode, questionsDict);

        const containsQuestion = (nodes) => nodes.some(node =>
          node.key === qKey || containsQuestion(node.subQuestions || [])
        );
        const sectionIdx = formStructure.findIndex(section => containsQuestion(section.questions));
        setCurrentStep(Math.max(0, sectionIdx) + 1);
        setFocusedQuestion(qKey);
        setActiveHighlight(highlights[qKey] || null);

        await sleep(800);
        await typeValue(qKey, targetVal, checkMounted);
        await sleep(1000);
      }

      if (!checkMounted()) return;
      setCurrentStep(totalSteps - 1);
      setFocusedQuestion('risk-result');
      setActiveHighlight(highlights.risk_result);
    };

    if (isAutoPlaying) {
      runSimulation();
    }

    return () => { isMounted = false; };
  }, [ready, isAutoPlaying, simulationKey, demoContent, demoForm, databaseConsent]);

  if (demoError) return <div className="demo-loading" role="alert">Unable to load the Version 2 guided tour: {demoError}</div>;
  if (!ready || !demoContent || !demoForm || !databaseConsent) return <div className="demo-loading">Preparing Version 2 Guided Tour...</div>;

  const renderTooltip = (key) => {
    if (focusedQuestion === key && activeHighlight) {
      return (
        <div className="demo-context-tooltip fade-in">
          <div className="tooltip-header"><Info size={16} /><span>{activeHighlight.title}</span></div>
          <div className="tooltip-body">{activeHighlight.highlight}</div>
          <div className="tooltip-arrow"></div>
        </div>
      );
    }
    return null;
  };

  const Riskometer = ({ riskLevel }) => {
    const [needleRotation, setNeedleRotation] = useState(-90);
    useEffect(() => {
      const timer = setTimeout(() => {
        const angles = { "Baseline Risk": -67.5, "Evident Risk": -22.5, "Significant Risk": 22.5, "High Risk": 67.5 };
        setNeedleRotation(angles[riskLevel] || 67.5);
      }, 800);
      return () => clearTimeout(timer);
    }, [riskLevel]);

    return (
      <div className="riskometer-container fade-in">
        <div className="riskometer-gauge">
          <div className="gauge-background"></div>
          <div className="riskometer-needle" style={{ transform: `rotate(${needleRotation}deg)` }}></div>
          <div className="riskometer-center"></div>
        </div>
        <div className="gauge-labels">
          <span className={riskLevel === "Baseline Risk" ? "active-level" : ""}>Baseline</span>
          <span className={riskLevel === "Evident Risk" ? "active-level" : ""}>Evident</span>
          <span className={riskLevel === "Significant Risk" ? "active-level" : ""}>Significant</span>
          <span className={riskLevel === "High Risk" ? "active-level" : ""}>High</span>
        </div>
      </div>
    );
  };

  const renderMockInput = (qNode) => {
    const qData = questionsDict[qNode.key];
    if (!qData) return null;
    const value = typedValues[qNode.key];

    if (qNode.type === 'hospital-select') {
      const demoInstitutes = ['Institute 1', 'Institute 2', 'Institute 3', 'Institute 4'];
      return (
        <div className="mock-input-wrapper">
          <select className={`mock-text-input ${value ? 'has-value' : ''}`} value={value || ''} readOnly>
            <option value="" disabled>Select an option</option>
            {[value, ...demoInstitutes].filter(Boolean).filter((name, idx, all) => all.indexOf(name) === idx).map((name, idx) => <option key={idx} value={name}>{name}</option>)}
          </select>
        </div>
      );
    }

    if (qData.answers?.length) {
      return (
        <div className="mock-options">
          {qData.answers.map((ans, idx) => {
            const isSelected = value === ans;
            if (ans === 'Yes') return <div key={idx} className={`binary-icon-box yes ${isSelected ? 'selected pulse-teal' : ''}`}><CheckCircle size={24} /><span>Yes</span></div>;
            if (ans === 'No') return <div key={idx} className={`binary-icon-box no ${isSelected ? 'selected pulse-teal' : ''}`}><div className="close-icon-wrap">&#10005;</div><span>No</span></div>;
            return <label key={idx} className={`mock-radio-label ${isSelected ? 'mock-selected pulse-teal' : ''}`}><input type="radio" checked={isSelected} readOnly /><span>{ans}</span></label>;
          })}
        </div>
      );
    } else {
      return <div className="mock-input-wrapper"><input type="text" className={`mock-text-input ${value ? 'has-value' : ''}`} value={value || ''} readOnly placeholder="Filling..." /></div>;
    }
  };

  const renderQuestion = (qNode, depth = 0) => {
    const questionText = questionsDict[qNode.key]?.question || qNode.key;
    const isFocused = focusedQuestion === qNode.key;
    const hasValue = typedValues[qNode.key] !== undefined;
    if (!hasValue && !isFocused) return null;

    return (
      <div key={qNode.key} className={`demo-question fade-in ${isFocused ? 'focused' : ''}`} style={{ marginLeft: `${depth * 20}px` }}>
        {isFocused && renderTooltip(qNode.key)}
        <div className="demo-question-text">{questionText}</div>
        <div className="demo-question-input">{renderMockInput(qNode)}</div>
        {qNode.subQuestions && qNode.subQuestions.length > 0 && (
          <div className="demo-subquestions">{qNode.subQuestions.map(subQ => renderQuestion(subQ, depth + 1))}</div>
        )}
      </div>
    );
  };

  const handleRestart = () => {
    setCurrentStep(0);
    setConsentChecked(false);
    setTypedValues({});
    setFocusedQuestion(null);
    setActiveHighlight(null);
    setIsAutoPlaying(true);
    setSimulationKey(prev => prev + 1);
    setDemoPhase('init');
  };

  const skipToResult = () => {
    setIsAutoPlaying(false);
    setCurrentStep(totalSteps - 1);
    setFocusedQuestion('risk-result');
    setActiveHighlight(highlights.risk_result);
  };

  return (
    <div className="demo-page-wrapper">
      {currentStep < totalSteps - 1 && (
        <div className="demo-progress-bar">
          <div className="demo-progress-fill" style={{ width: `${(currentStep / (totalSteps - 1)) * 100}%` }}></div>
        </div>
      )}

      <div className="demo-main-single-column">
        <div className="demo-content-card">
          <div className="demo-card-header">
            <div className="demo-header-brands">
              <img src="/tanuh.png" alt="Tanuh" className="brand-logo logo-tanuh" />
              <div className="brand-divider"></div>
              <img src="/MoE_Logo.svg" alt="MoE" className="brand-logo logo-moe" />
              <div className="brand-divider"></div>
              <img src="/IISc_logo.png" alt="IISc" className="brand-logo logo-iisc" />
            </div>
          </div>

          <div className="demo-step-box">
            {currentStep === 0 && (
              <div className="demo-step-content fade-in consent-demo-view">
                <div className="demo-step-nav-header demo-step-nav-header-consent">
                  <h2>{consentData.title}</h2>
                  <div className="demo-mock-lang" style={{ position: 'relative' }}>
                    <div className="lang-trigger">&#127760; {langSelected || 'Select Language...'}</div>
                  </div>
                </div>
                <div className="consent-scroll-container" ref={scrollRef}>
                  <div className="consent-header-info">
                    <p><strong>{consentData.headernames?.studyTitle || 'Study Title'}:</strong> {consentData.header?.studyTitle}</p>
                    <p><strong>{consentData.headernames?.sponsor || 'Organiser and Funder'}:</strong> {consentData.header?.sponsor}</p>
                    <p><strong>{consentData.headernames?.iecApproval || 'Ethics Review'}:</strong> {consentData.header?.iecApproval}</p>
                  </div>
                  {consentData.sections?.map((section, idx) => (
                    <div key={idx} className={section.className || 'consent-section-demo'}>
                      <h3>{section.heading}</h3>
                      {section.paragraphs?.map((para, pIdx) => (
                        <p key={pIdx} className={para.className || ''}>{para.strong && <strong>{para.strong} </strong>}{para.text}</p>
                      ))}
                    </div>
                  ))}
                  {consentData.informedConsent && (
                    <section className="informed-consent-demo">
                      <h2>{consentData.informedConsent.title}</h2>
                      <div className="consent-header-info">
                        {Object.values(consentData.informedConsent.projectDetails || {}).map((detail, idx) => (
                          <p key={idx}><strong>{detail.label}:</strong> {detail.value}</p>
                        ))}
                      </div>
                      {consentData.informedConsent.sections?.map((section, idx) => (
                        <div key={idx} className="consent-section-demo">
                          <h3>{section.heading}</h3>
                          {section.paragraphs?.map((paragraph, pIdx) => <p key={pIdx}>{paragraph.text}</p>)}
                        </div>
                      ))}
                      <div className="consent-section-demo">
                        <h3>{consentData.informedConsent.participantConsentHeading}</h3>
                        <p>{consentData.informedConsent.declaration}</p>
                        <label className={`mock-check-lbl ${demoPhase === 'checkbox-blinking' ? 'pulse-teal' : ''}`}>
                          <input type="checkbox" checked={consentChecked} readOnly />
                          <span>{consentData.informedConsent.ageCheckboxLabel}</span>
                        </label>
                        <label className={`mock-check-lbl ${demoPhase === 'checkbox-blinking' ? 'pulse-teal' : ''}`}>
                          <input type="checkbox" checked={consentChecked} readOnly />
                          <span>{consentData.informedConsent.voluntaryCheckboxLabel}</span>
                        </label>
                      </div>
                    </section>
                  )}
                </div>
                <div className="demo-consent-upload-mock fade-in">
                  <strong className="demo-consent-upload-title">Consent Upload</strong>
                  <div className="demo-upload-buttons">
                    <div className="demo-upload-btn filled">
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
                      <span>Take Photo</span>
                    </div>
                    <div className="demo-upload-btn outlined">
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                      <span>Upload Image</span>
                    </div>
                  </div>
                </div>

                <div className="demo-consent-bottom">
                  {!consentData.informedConsent && (
                    <label className={`mock-check-lbl ${demoPhase === 'checkbox-blinking' ? 'pulse-teal' : ''}`}>
                      <input type="checkbox" checked={consentChecked} readOnly /><span>{consentData.checkboxLabel}</span>
                    </label>
                  )}
                  <button className={`btn-premium ${demoPhase === 'button-blinking' ? 'pulse-teal' : ''}`} disabled={!consentChecked}>{consentData.buttonText}</button>
                </div>
              </div>
            )}

            {currentStep > 0 && currentStep <= (Array.isArray(formStructure) ? formStructure.length : 0) && (
              <div className="demo-step-content fade-in">
                <div className="demo-step-nav-header">
                  <h2>{formStructure[currentStep - 1].title}</h2>
                  <span className="demo-badge">Version 2 Guided Tour</span>
                </div>
                <div className="demo-questions-viewport">
                  {formStructure[currentStep - 1].questions.map(q => renderQuestion(q))}
                </div>
              </div>
            )}

            {currentStep === totalSteps - 1 && (
              <div className="demo-step-content fade-in thank-you-dialog">
                {renderTooltip('risk-result')}
                <div className="demo-result-header-centered">
                  <div className="thank-you-header"><CheckCircle className="success-icon" size={48} /><h3>Submission Complete</h3></div>
                  <p className="demo-thank-you-msg">Thank you for completing the questionnaire!</p>
                  <div className="demo-risk-status-hero"><h2 className="risk-status-text">{userRiskLevel}</h2></div>
                </div>
                <Riskometer riskLevel={userRiskLevel} />
                <div className="what-to-do-container">
                  <h4 className="what-to-do-title">{tThankYou('interpretation.headers.action')}</h4>
                  {highlightedRow ? <div className="what-to-do-box"><p className="what-to-do-text">{highlightedRow.action}</p></div> : <p className="no-data-text">No specific action available.</p>}
                </div>
                <div style={{ display: 'flex', width: '100%' }}><RiskTable /></div>
                <p className="disclaimer-text"><span className="disclaimer-asterisk">{tThankYou('disclaimer.asterisk')}</span><strong>{tThankYou('disclaimer.title')}</strong>: {tThankYou('disclaimer.text')}</p>
                <div className="demo-footer-actions" style={{ display: 'flex', flexDirection: 'column', gap: '15px', width: '100%', alignItems: 'center' }}>
                  <button className="btn-secondary" style={{ width: '100%' }} onClick={handleRestart}>Restart Tour &#8635;</button>
                  <button className="btn-premium" style={{ width: '100%' }} disabled>Download Results PDF &#11015;</button>
                </div>
              </div>
            )}
          </div>

          {currentStep < totalSteps - 1 && (
            <div className="demo-bottom-controls">
              <button className="btn-ghost" onClick={skipToResult}>Skip to Result &#10132;</button>
              <div className="auto-play-indicator">
                <div className="pulse-dot"></div>
                {isAutoPlaying ? 'Guided Tour in Progress...' : 'Tour Paused'}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Demo;
