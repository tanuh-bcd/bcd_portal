import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import Consent from '../components/Consent.jsx';
import Questionnaire from '../components/Questionnaire.jsx';
import ThankYou from '../components/ThankYou.jsx';

const API_URL = process.env.REACT_APP_API_URL || '';

const PublicQuestionnairePage = ({ lockedHospitalName = '' }) => {
  const [step, setStep] = useState('consent');
  const [sessionId, setSessionId] = useState(null);
  const [questionnaireVersion, setQuestionnaireVersion] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [riskResult, setRiskResult] = useState(null);
  const [finalFormData, setFinalFormData] = useState(null);

  const { t, i18n, ready } = useTranslation(['consent', 'questionnaire', 'thankyou']);
  const [databaseQuestions, setDatabaseQuestions] = useState(null);
  const [questionLoadError, setQuestionLoadError] = useState('');

  const languageCodes = {
    english: 'en', hindi: 'hi', bengali: 'bn', gujarati: 'gu', kannada: 'kn',
    malayalam: 'ml', marathi: 'mr', odia: 'or', punjabi: 'pa', tamil: 'ta', telugu: 'te',
    en: 'en', hi: 'hi', bn: 'bn', gu: 'gu', kn: 'kn', ml: 'ml', mr: 'mr',
    or: 'or', pa: 'pa', ta: 'ta', te: 'te',
  };
  const languageCode = languageCodes[i18n.resolvedLanguage || i18n.language] || 'en';

  useEffect(() => {
    let cancelled = false;
    const loadQuestions = async () => {
      try {
        setQuestionLoadError('');
        const query = new URLSearchParams({ lang: languageCode });
        const questionnaireVersion = process.env.REACT_APP_QUESTIONNAIRE_VERSION;
        if (questionnaireVersion) query.set('version', questionnaireVersion);

        const response = await fetch(`${API_URL}/api/v1/patient/questions?${query.toString()}`);
        if (!response.ok) throw new Error(`Questionnaire request failed (${response.status})`);
        const rows = await response.json();
        if (!cancelled) setDatabaseQuestions(rows);
      } catch (error) {
        if (!cancelled) setQuestionLoadError(error.message);
      }
    };
    loadQuestions();
    return () => { cancelled = true; };
  }, [languageCode]);

  const databaseForm = useMemo(() => {
    if (!Array.isArray(databaseQuestions)) return null;
    const localized = {};
    const english = {};
    const configs = new Map();

    databaseQuestions.forEach(row => {
      const key = row.question_key;
      const isRepeatedTrimesterQuestion = key === 'V2_Q13C_TRIMESTERS'
        || key === 'V2_Q13D_TRIMESTERS';
      const isEthnicityQuestion = key === 'V2_Q18';
      const isInstitutionQuestion = key === 'V2_Q02';
      localized[key] = { question: row.question_text, answers: row.options.map(option => option.option_label) };
      english[key] = { question: row.question_text, answers: row.options.map(option => option.option_value) };
      configs.set(row.id, {
        key,
        type: isInstitutionQuestion
          ? 'hospital-select'
          : isRepeatedTrimesterQuestion
          ? 'repeat_select'
          : (isEthnicityQuestion
            ? 'compact_dropdown'
            : (row.input_type || (row.response_type === 'numbers_only' ? 'number' : 'text'))),
        required: row.is_required,
        min: row.min_value == null ? undefined : Number(row.min_value),
        max: row.max_value == null ? undefined : Number(row.max_value),
        step: row.step_value == null ? undefined : Number(row.step_value),
        placeholder: row.placeholder || undefined,
        videoUrlOnNo: row.video_url || undefined,
        otherOptionId: row.other_option_id || undefined,
        otherPlaceholder: row.other_placeholder || undefined,
        parentId: row.parent_question_id,
        triggerAnswer: row.trigger_answer,
        section: row.section || 'Questionnaire',
        subQuestions: [],
      });
    });

    const sections = new Map();
    databaseQuestions.forEach(row => {
      const config = configs.get(row.id);
      if (config.parentId && configs.has(config.parentId)) {
        const parent = configs.get(config.parentId);
        if (config.type === 'repeat_select') config.repeatCountKey = parent.key;
        if (config.triggerAnswer) config.condition = { key: parent.key, value: config.triggerAnswer };
        parent.subQuestions.push(config);
      } else {
        if (!sections.has(config.section)) sections.set(config.section, []);
        sections.get(config.section).push(config);
      }
    });

    return {
      formStructure: Array.from(sections, ([title, questions]) => ({ title, questions })),
      localized,
      english,
    };
  }, [databaseQuestions]);

  const fallbackStructure = ready ? t('questionnaire:formStructure', { returnObjects: true }) : [];
  const fallbackQuestions = ready ? t('questionnaire:questions', { returnObjects: true }) : {};
  const formStructure = databaseForm?.formStructure || fallbackStructure;
  const questionnaireData = databaseForm?.localized || fallbackQuestions;
  const questionnaireDataEn = databaseForm?.english || fallbackQuestions;

  const handleConsentAccept = async (result) => {
    try {
      const questionnaireVersion = process.env.REACT_APP_QUESTIONNAIRE_VERSION;
      const query = new URLSearchParams();
      if (questionnaireVersion) query.set('version', questionnaireVersion);
      const suffix = query.toString() ? `?${query.toString()}` : '';
      const res = await fetch(`${API_URL}/api/session/start${suffix}`, { method: 'POST' });
      const data = await res.json();
      if (data.success && data.sessionId) {
        setSessionId(data.sessionId);
        setQuestionnaireVersion(Number(data.questionnaireVersion || questionnaireVersion || 1));

        if (result && result.file) {
          const formData = new FormData();
          formData.append('file', result.file);
          fetch(`${API_URL}/api/session/${data.sessionId}/consent`, {
            method: 'POST',
            body: formData,
          }).catch(() => {});
        }

        setStep('questionnaire');
        window.scrollTo(0, 0);
      } else {
        alert('Could not start a session. Please try again.');
      }
    } catch (error) {
      alert('Could not connect to the server. Please try again.');
    }
  };

  const handleSubmit = async (formData, formDataEn) => {
    if (!sessionId) return;
    setIsSubmitting(true);
    setFinalFormData(formDataEn || formData);

    const submitData = formDataEn || formData;
    const MAX_RETRIES = 2;

    for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
      try {
        const res = await fetch(`${API_URL}/api/submit`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ sessionId, formDataEn: submitData }),
        });
        if (!res.ok) {
          const errorData = await res.json().catch(() => ({}));
          const detail = Array.isArray(errorData.detail)
            ? errorData.detail.map(e => e.msg || e.type).join('; ')
            : errorData.detail || 'Server error';
          if (res.status >= 500 && attempt < MAX_RETRIES) {
            await new Promise(r => setTimeout(r, 1000 * (attempt + 1)));
            continue;
          }
          alert(`Submission failed: ${detail}. Please try again.`);
          setFinalFormData(null);
          setIsSubmitting(false);
          return;
        }
        const result = await res.json();
        if (result.success) {
          setQuestionnaireVersion(Number(result.questionnaireVersion || questionnaireVersion || 1));
          setRiskResult(result.riskCalculated ? result.riskPercentage : null);
          setStep('thankyou');
          window.scrollTo(0, 0);
        } else {
          alert('Submission failed. Please try again.');
          setFinalFormData(null);
        }
        setIsSubmitting(false);
        return;
      } catch (error) {
        if (attempt < MAX_RETRIES) {
          await new Promise(r => setTimeout(r, 1000 * (attempt + 1)));
          continue;
        }
        alert('Could not connect to the server. Please try again.');
        setFinalFormData(null);
        setIsSubmitting(false);
        return;
      }
    }
  };

  const handleReset = () => {
    setStep('consent');
    setSessionId(null);
    setQuestionnaireVersion(null);
    setRiskResult(null);
    setFinalFormData(null);
  };

  if (!ready) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
        Loading...
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', justifyContent: 'center', padding: '20px 16px', width: '100%' }}>
      {step === 'consent' && <Consent onAccept={handleConsentAccept} />}
      {step === 'questionnaire' && (
        <Questionnaire
          onSubmit={handleSubmit}
          isSubmitting={isSubmitting}
          formStructure={formStructure}
          questionnaireData={questionnaireData}
          questionnaireDataEn={questionnaireDataEn}
          lockedHospitalName={lockedHospitalName}
        />
      )}
      {questionLoadError && step === 'consent' && (
        <div style={{ color: '#b42318', marginTop: 12 }}>Could not load active questionnaire: {questionLoadError}</div>
      )}
      {step === 'thankyou' && (
        <ThankYou
          riskResult={riskResult}
          formData={finalFormData}
          sessionId={sessionId}
          onReset={handleReset}
          formStructure={Array.isArray(formStructure) ? formStructure : []}
          questionnaireData={questionnaireData}
          dataCollectionOnly={false}
        />
      )}
    </div>
  );
};

export default PublicQuestionnairePage;
