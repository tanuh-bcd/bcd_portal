import React, { memo, useEffect, useRef, useState } from 'react';

const OPTION_TOOLTIPS = {
  'Post-hysterectomy': 'postHysterectomy',
  'Post-oophorectomy': 'postOophorectomy',
};

// Optimization: Extracted this component to apply React.memo.
// The Questionnaire component renders many of these blocks.
// Memoization prevents re-rendering all questions when typing in a single field,
// provided the custom comparator filters out unrelated state changes.
const QuestionBlock = ({
  qConfig,
  questionnaireData,
  questionnaireDataEn,
  formData,
  formDataEn,
  validationErrors,
  handleChange,
  handleRepeatChange,
  t,
  displayNumber,
  randomPatientId, // NEW: Passed prop
  hospitals,
  // Q27 specific props
  isQ27No,
  showQ27VideoPrompt,
  q27VideoConfirmed,
  setQ27VideoConfirmed,
}) => {
  const name = qConfig.name || qConfig.key;
  const data = questionnaireData[qConfig.key];
  const isYouTubeEmbed = Boolean(qConfig.videoUrlOnNo)
    && /(?:youtube\.com\/embed\/|youtu\.be\/)/i.test(qConfig.videoUrlOnNo);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const dropdownRef = useRef(null);

  const getOtherFieldName = (config, qName) => config.otherOptionId || `${qName}__other`;
  const otherIsSelected = (qName, checkbox = false) => {
    const englishValue = formDataEn[qName];
    return checkbox
      ? Array.isArray(englishValue) && englishValue.some(value => /^others?$/i.test(String(value).trim()))
      : /^others?$/i.test(String(englishValue || '').trim());
  };
  const renderOtherInput = (config, qName) => {
    const otherFieldName = getOtherFieldName(config, qName);
    return (
      <input
        type="text"
        name={otherFieldName}
        placeholder={config.otherPlaceholder || t('ui.inputs.otherPlaceholder', 'Please specify')}
        onChange={handleChange}
        className="text-input other-specify-input"
        value={formData[otherFieldName] || ''}
      />
    );
  };

  useEffect(() => {
    if (!isDropdownOpen) return undefined;
    const closeOnOutsideClick = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', closeOnOutsideClick);
    return () => document.removeEventListener('mousedown', closeOnOutsideClick);
  }, [isDropdownOpen]);

  if (!data) return <p>{t('ui.errors.questionNotFound', { key: qConfig.key })}</p>;

  // --- renderInput Logic ---
  const renderInput = (config) => {
    const qName = config.name || config.key;
    const qData = questionnaireData[config.key];
    if (!qData) return null;

    // A group is a display-only parent used to number related child fields.
    if (config.type === 'group') return null;

    let placeholder = config.placeholder || '';
    if (config.key === 'Q44') {
      // FIX: Use the prop for placeholder
      placeholder = randomPatientId;
    }

    if (config.type === 'hospital-select') {
      return (
        <select name={qName} onChange={handleChange} value={formData[qName] || ""} className="select-input">
          <option value="" disabled>{t('ui.inputs.selectDefault')}</option>
          {(hospitals || []).map((h) => <option key={h.id} value={h.name}>{h.name}</option>)}
        </select>
      );
    }

    if (config.type === 'number_or_unknown') {
      const unknownAnswer = qData.answers.find(answer => answer === "I don't know") || "I don't know";
      const currentValue = formData[qName];
      return (
        <>
          <input
            type="number"
            name={qName}
            placeholder={placeholder}
            value={currentValue === unknownAnswer ? '' : (currentValue || '')}
            onChange={handleChange}
            className="text-input"
            min={config.min}
            max={config.max}
            step={config.step}
          />
          <label style={{ display: 'block', marginTop: '10px' }}>
            <input
              type="radio"
              name={qName}
              value={unknownAnswer}
              checked={currentValue === unknownAnswer}
              onChange={handleChange}
            />{' '}
            {unknownAnswer}
          </label>
          {validationErrors.includes(qName) && (
            <div className="field-error">{t('ui.invalidInput.validInput')}</div>
          )}
        </>
      );
    }

    if (!Array.isArray(qData.answers) || qData.answers.length === 0) {
      if (config.type === 'number') {
        const minAttr = config.min !== undefined ? config.min : undefined;
        const maxAttr = config.max !== undefined ? config.max : undefined;
        const stepAttr = config.step !== undefined ? config.step : undefined;

        return (
          <>
            <input
              type="number"
              name={qName}
              placeholder={placeholder}
              value={formData[qName] || ''}
              onChange={handleChange}
              onKeyDown={(e) => {
                if (config.integerOnly && (e.key === '.' || e.key === ',')) {
                  e.preventDefault();
                }
              }}
              className="text-input"
              min={minAttr}
              max={maxAttr}
              step={stepAttr}
            />
            {validationErrors.includes(qName) && (
              <div className="field-error">
                {config.min !== undefined && config.max !== undefined
                  ? `${t('ui.invalidInput.numberPrefix')} ${config.min} ${t('ui.invalidInput.and')} ${config.max}.`
                  : `${t('ui.invalidInput.validInput')} `}
              </div>
            )}
          </>
        );
      }
      return (
        <input
          type={config.type || 'text'}
          name={qName}
          placeholder={placeholder}
          value={formData[qName] || ''}
          onChange={handleChange}
          className="text-input"
        />
      );
    }

    switch (config.type) {
      case 'compact_dropdown': {
        const selectedValue = formData[qName] || '';
        const renderEthnicityLabel = (answer) => {
          const separator = answer.includes(' — ') ? ' — ' : (answer.includes(' - ') ? ' - ' : null);
          if (!separator) return <strong>{answer}</strong>;
          const [category, ...details] = answer.split(separator);
          return (
            <>
              <strong>{category}</strong>
              <span>{separator}{details.join(separator)}</span>
            </>
          );
        };

        return (
          <>
            <div className="compact-dropdown" ref={dropdownRef}>
              <button
              type="button"
              className="compact-dropdown-toggle"
              aria-haspopup="listbox"
              aria-expanded={isDropdownOpen}
              onClick={() => setIsDropdownOpen(open => !open)}
            >
              <span>{selectedValue ? renderEthnicityLabel(selectedValue) : t('ui.inputs.selectDefault')}</span>
              <span className="compact-dropdown-arrow" aria-hidden="true">⌄</span>
              </button>
              {isDropdownOpen && (
                <div className="compact-dropdown-menu" role="listbox">
                {qData.answers.map((answer, index) => (
                  <button
                    type="button"
                    role="option"
                    aria-selected={selectedValue === answer}
                    className={`compact-dropdown-option ${selectedValue === answer ? 'selected' : ''}`}
                    key={index}
                    onClick={() => {
                      handleChange({ target: { name: qName, value: answer, type: 'radio', checked: true } });
                      setIsDropdownOpen(false);
                    }}
                  >
                    {renderEthnicityLabel(answer)}
                  </button>
                ))}
                </div>
              )}
            </div>
            {otherIsSelected(qName) && renderOtherInput(config, qName)}
          </>
        );
      }
      case 'repeat_select': {
        const count = Math.max(0, Math.min(120, Number.parseInt(formData[config.repeatCountKey], 10) || 0));
        const selectedValues = Array.isArray(formData[qName]) ? formData[qName] : [];
        const itemLabel = config.otherPlaceholder || 'Entry';
        return (
          <div className="repeat-select-group">
            {Array.from({ length: count }, (_, index) => (
              <div key={index} style={{ marginBottom: '12px' }}>
                <label htmlFor={`${qName}-${index}`} style={{ display: 'block', marginBottom: '6px' }}>
                  {itemLabel} {index + 1}
                </label>
                <select
                  id={`${qName}-${index}`}
                  name={`${qName}-${index}`}
                  value={selectedValues[index] || ''}
                  onChange={(event) => handleRepeatChange(qName, index, event.target.value)}
                  className="select-input"
                >
                  <option value="" disabled>{t('ui.inputs.selectDefault')}</option>
                  {qData.answers.map((answer, answerIndex) => (
                    <option key={answerIndex} value={answer}>{answer}</option>
                  ))}
                </select>
              </div>
            ))}
          </div>
        );
      }
      case 'select':
      case 'select-plus-text':
        return (
          <>
            <select name={qName} onChange={handleChange} value={formData[qName] || ""} className="select-input">
              <option value="" disabled>{t('ui.inputs.selectDefault')}</option>
              {qData.answers.map((ans, i) => <option key={i} value={ans}>{ans}</option>)}
            </select>
            {otherIsSelected(qName) && renderOtherInput(config, qName)}
          </>
        );
      case 'checkbox':
      case 'checkbox-plus-text':
        return (
          <div className="checkbox-group vertical">
            {qData.answers.map((ans, i) => {
              const isOtherOption = /^others?$/i.test(String(questionnaireDataEn[config.key]?.answers?.[i] || ans).trim());
              return (
                <React.Fragment key={i}>
                  <label>
                    <input
                      type="checkbox" name={qName} value={ans} onChange={handleChange}
                      checked={formData[qName]?.includes(ans) || false}
                    /> {ans}
                  </label>
                  {isOtherOption && otherIsSelected(qName, true) && renderOtherInput(config, qName)}
                </React.Fragment>
              );
            })}
          </div>
        );
      case 'radio':
      default:
        return (
          <div className="radio-group vertical">
            {qData.answers.map((ans, i) => {
              const englishAnswer = questionnaireDataEn[config.key]?.answers?.[i] || ans;
              const isOtherOption = /^others?$/i.test(String(englishAnswer).trim());
              const tooltipKey = OPTION_TOOLTIPS[englishAnswer];
              const tooltip = tooltipKey ? t(`ui.tooltips.${tooltipKey}`) : undefined;
              return (
                <React.Fragment key={i}>
                  <label
                    className={tooltip ? 'question-option-with-tooltip' : undefined}
                    data-tooltip={tooltip}
                  >
                    <input
                      type="radio" name={qName} value={ans} onChange={handleChange}
                      checked={formData[qName] === ans}
                      aria-label={tooltip ? `${ans}. ${tooltip}` : undefined}
                    /> {ans}
                  </label>
                  {isOtherOption && otherIsSelected(qName) && renderOtherInput(config, qName)}
                </React.Fragment>
              );
            })}
          </div>
        );
    }
  };

  return (
    <React.Fragment>
      <div className={`question-block ${validationErrors.includes(name) ? 'error' : ''}`}>
        <label>
          {displayNumber} {data.question}
          {qConfig.required && <span className="required-asterisk">*</span>}
        </label>
        {renderInput(qConfig)}
      </div>

      {qConfig.key === 'V2_Q19A'
        && formDataEn[name] === 'Yes'
        && qConfig.videoUrlOnNo && (
          <div className="self-exam-video-container">
            {isYouTubeEmbed ? (
              <iframe
                src={qConfig.videoUrlOnNo}
                title="Self Breast Examination demonstration"
                allow="autoplay; encrypted-media; picture-in-picture"
                allowFullScreen
              />
            ) : (
              <video
                controls
                preload="metadata"
                src={qConfig.videoUrlOnNo}
                title="Self Breast Examination demonstration"
              >
                Your browser does not support the video tag.
              </video>
            )}
          </div>
      )}

      {qConfig.key === "Q27" && isQ27No && (
        <>
          {!q27VideoConfirmed && showQ27VideoPrompt && (
            <div className="video-prompt-container">
              <p className="video-prompt-note">{t('ui.videoPrompt.note')}</p>
              <button
                type="button"
                className="video-prompt-button"
                onClick={() => setQ27VideoConfirmed(true)}
              >
                {t('ui.videoPrompt.button')}
              </button>
            </div>
          )}
          {q27VideoConfirmed && qConfig.videoUrlOnNo && (
            <div className="video-container">
              <video width="100%" controls autoPlay src={qConfig.videoUrlOnNo} title={t('ui.videoPrompt.videoTitle')} style={{ borderRadius: 8, maxHeight: 400 }}>
                Your browser does not support the video tag.
              </video>
            </div>
          )}
        </>
      )}
    </React.Fragment>
  );
};

// Custom Comparator
const arePropsEqual = (prev, next) => {
  const name = next.qConfig.name || next.qConfig.key;

  // 1. Check strict dependencies (including i18n)
  if (prev.t !== next.t) return false; // FIX: Language change detection
  if (prev.questionnaireData !== next.questionnaireData) return false; // FIX: Data change

  if (prev.qConfig !== next.qConfig) return false;
  if (prev.displayNumber !== next.displayNumber) return false;
  if (prev.validationErrors.includes(name) !== next.validationErrors.includes(name)) return false;

  if (prev.randomPatientId !== next.randomPatientId) return false; // FIX: Q44 dependency
  if (prev.hospitals !== next.hospitals) return false;

  // 2. Check value change
  if (prev.formData[name] !== next.formData[name]) return false;
  if (prev.formDataEn[name] !== next.formDataEn[name]) return false;
  if (next.qConfig.repeatCountKey
      && prev.formData[next.qConfig.repeatCountKey] !== next.formData[next.qConfig.repeatCountKey]) return false;

  // 3. Check Q27 specifics
  if (name === 'Q27') {
    if (prev.isQ27No !== next.isQ27No) return false;
    if (prev.showQ27VideoPrompt !== next.showQ27VideoPrompt) return false;
    if (prev.q27VideoConfirmed !== next.q27VideoConfirmed) return false;
  }

  // 4. Subquestions check
  // Removed recursive subquestions check because QuestionBlock no longer renders them.
  // Instead, Questionnaire.jsx handles the tree.

  // 5. Other specify field check
  const otherKey = next.qConfig.otherOptionId || `${name}__other`;
  if (prev.formData[otherKey] !== next.formData[otherKey]) return false;

  return true;
};

export default memo(QuestionBlock, arePropsEqual);
