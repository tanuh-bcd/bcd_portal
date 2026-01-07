import React, { useState, useEffect } from 'react';
import './Questionnaire.css';
import { useTranslation } from 'react-i18next';
import LanguageSwitcher from './LanguageSwitcher';

function Questionnaire({ onSubmit, isSubmitting }) {
  const { t, i18n } = useTranslation('questionnaire');
  
  // State for form data (localized)
  const [formData, setFormData] = useState({});
  // State for form data (always English for logic/backend)
  const [formDataEn, setFormDataEn] = useState({});
  const [validationErrors, setValidationErrors] = useState([]);
  const [q27VideoConfirmed, setQ27VideoConfirmed] = useState(false);
  const [showQ27VideoPrompt, setShowQ27VideoPrompt] = useState(false);

  const formStructure = t('formStructure', { returnObjects: true });
  const questions = t('questions', { returnObjects: true });

  // Get English version for logic
  const tEn = i18n.getFixedT('en', 'questionnaire');
  const questionsEn = tEn('questions', { returnObjects: true });

  useEffect(() => {
    // Initialize default values if any
    const defaults = t('ui.defaults', { returnObjects: true });
    if (defaults.q45) {
      setFormData(prev => ({ ...prev, Q45: defaults.q45 }));
      setFormDataEn(prev => ({ ...prev, Q45: tEn('ui.defaults.q45') }));
    }
  }, [t, tEn]);

  const handleInputChange = (key, value, type) => {
    setFormData(prev => ({ ...prev, [key]: value }));
    
    // Convert value to English for formDataEn if it's a choice-based input
    let valueEn = value;
    if (type === 'radio' || type === 'select') {
      const questionData = questions[key];
      const questionDataEn = questionsEn[key];
      if (questionData && questionDataEn && questionData.answers) {
        const index = questionData.answers.indexOf(value);
        if (index !== -1) {
          valueEn = questionDataEn.answers[index];
        }
      }
    }
    
    setFormDataEn(prev => ({ ...prev, [key]: valueEn }));

    if (key === "Q27") {
        const noValueEn = tEn('questions.Q27.answers.1');
        if (valueEn === noValueEn) {
            setShowQ27VideoPrompt(true);
        } else {
            setShowQ27VideoPrompt(false);
            setQ27VideoConfirmed(false);
        }
    }

    if (validationErrors.includes(key)) {
      setValidationErrors(prev => prev.filter(k => k !== key));
    }
  };

  const validate = () => {
    const errors = [];
    const checkRequired = (qs) => {
      qs.forEach(q => {
        if (q.required && !formData[q.key]) {
          errors.push(q.key);
        }
        if (q.subQuestions) {
          const conditionValue = q.condition ? q.condition.value : null;
          if (!conditionValue || formDataEn[q.key] === conditionValue) {
            checkRequired(q.subQuestions);
          }
        }
      });
    };

    formStructure.forEach(section => checkRequired(section.questions));
    setValidationErrors(errors);
    return errors.length === 0;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (validate()) {
      // Map formDataEn to a list of {question, answer}
      const responses = [];
      const extractResponses = (qs) => {
        qs.forEach(qConfig => {
          const { key, subQuestions, condition } = qConfig;
          const questionDataEn = questionsEn[key];
          
          if (formDataEn[key] !== undefined) {
             // Only include if it was shown (condition met or no condition)
             const showSub = subQuestions && condition && formDataEn[condition.key] === condition.value;
             
             responses.push({
               question: questionDataEn.question,
               answer: String(formDataEn[key])
             });

             if (showSub) {
               extractResponses(subQuestions);
             }
          }
        });
      };

      formStructure.forEach(section => extractResponses(section.questions));
      onSubmit(responses);
    } else {
      alert(t('ui.errors.validationAlert'));
    }
  };

  const renderInput = (qConfig) => {
    const { key, type, placeholder, min, max, step } = qConfig;
    const questionData = questions[key];
    if (!questionData) return null;

    switch (type) {
      case 'text':
      case 'number':
        return (
          <input
            type={type}
            placeholder={placeholder}
            value={formData[key] || ''}
            onChange={(e) => handleInputChange(key, e.target.value, type)}
            min={min}
            max={max}
            step={step}
            className={validationErrors.includes(key) ? 'error' : ''}
          />
        );
      case 'radio':
        return (
          <div className="radio-group">
            {questionData.answers.map((answer, i) => (
              <label key={i} className="radio-label">
                <input
                  type="radio"
                  name={key}
                  value={answer}
                  checked={formData[key] === answer}
                  onChange={(e) => handleInputChange(key, e.target.value, type)}
                />
                {answer}
              </label>
            ))}
          </div>
        );
      case 'select':
        return (
          <select
            value={formData[key] || ''}
            onChange={(e) => handleInputChange(key, e.target.value, type)}
            className={validationErrors.includes(key) ? 'error' : ''}
          >
            <option value="">{t('ui.inputs.selectDefault')}</option>
            {questionData.answers.map((answer, i) => (
              <option key={i} value={answer}>{answer}</option>
            ))}
          </select>
        );
      default:
        return null;
    }
  };

  const renderQuestions = (qs, counter) => {
    let currentCounter = counter;
    return qs.map((qConfig) => {
      const { key, subQuestions, condition, videoUrlOnNo } = qConfig;
      const questionData = questions[key];
      if (!questionData) return null;

      currentCounter++;
      const showSub = subQuestions && condition && formDataEn[condition.key] === condition.value;
      const isQ27No = key === "Q27" && formDataEn[key] === tEn('questions.Q27.answers.1');

      return (
        <React.Fragment key={key}>
          <div className={`question-block ${validationErrors.includes(key) ? 'error' : ''}`}>
            <label>
              {currentCounter}. {questionData.question}
              {qConfig.required && <span className="required-asterisk">*</span>}
            </label>
            {renderInput(qConfig)}
          </div>
          {showSub && (
            <div className="sub-question-container visible">
              {renderQuestions(subQuestions, currentCounter * 100)}
            </div>
          )}
          {key === "Q27" && isQ27No && (
            <div className="video-section">
              {!q27VideoConfirmed && showQ27VideoPrompt && (
                <div className="video-prompt">
                  <p>{t('ui.videoPrompt.note')}</p>
                  <button type="button" onClick={() => setQ27VideoConfirmed(true)}>
                    {t('ui.videoPrompt.button')}
                  </button>
                </div>
              )}
              {q27VideoConfirmed && videoUrlOnNo && (
                <div className="video-container">
                  <iframe 
                    width="100%" 
                    height="315" 
                    src={videoUrlOnNo} 
                    title={t('ui.videoPrompt.videoTitle')} 
                    frameBorder="0" 
                    allowFullScreen
                  ></iframe>
                </div>
              )}
            </div>
          )}
        </React.Fragment>
      );
    });
  };

  // Calculate progress
  const totalRequired = formStructure.reduce((acc, section) => 
    acc + section.questions.filter(q => q.required).length, 0);
  const filledRequired = formStructure.reduce((acc, section) => 
    acc + section.questions.filter(q => q.required && formData[q.key]).length, 0);
  const progress = totalRequired > 0 ? Math.round((filledRequired / totalRequired) * 100) : 0;

  return (
    <div className="questionnaire-page">
      <div className="progress-bar-container">
        <div className="progress-bar-text">
          {t('ui.progressBarTemplate', { progress })}
        </div>
        <div className="progress-bar-bg">
          <div className="progress-bar-fill" style={{ width: `${progress}%` }}></div>
        </div>
      </div>

      <form className="questionnaire-container" onSubmit={handleSubmit}>
        <LanguageSwitcher />

        <div className="form-header">
          <h1>{t('ui.header.title')}</h1>
          <p className="instructions">{t('ui.header.instructions')}</p>
          <p className="mandatory-note">
            {t('ui.header.mandatoryPre')}
            <span className="required-asterisk">{t('ui.header.mandatorySymbol')}</span>
            {t('ui.header.mandatoryPost')}
          </p>
        </div>

        {formStructure.map((section, idx) => (
          <div key={idx} className="form-section">
            <h2>{section.title}</h2>
            {renderQuestions(section.questions, idx * 10)}
          </div>
        ))}

        <div className="submit-section">
          <button 
            type="submit" 
            className={`submit-button ${isSubmitting ? 'loading' : ''}`}
            disabled={isSubmitting}
          >
            {isSubmitting ? t('ui.submitButton.loading') : t('ui.submitButton.default')}
          </button>
        </div>
      </form>
    </div>
  );
}

export default Questionnaire;
