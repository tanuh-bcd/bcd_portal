-- Questionnaire V2 content update. Production-safe: no COMMIT is issued.
-- Run against bcd_application2, inspect the final SELECTs, then COMMIT or ROLLBACK.
SET NAMES utf8mb4;
USE bcd_application2;
START TRANSACTION;

-- Q2 is rendered as a live hospital dropdown by the frontend. Hospital names
-- deliberately remain in the hospitals table rather than being copied here.
UPDATE questions
SET question = 'Enter the Institution Name (If any, else leave)',
    response_type = 'option', input_type = 'hospital-select', is_required = 0,
    placeholder = NULL
WHERE version_number = 2 AND question_key = 'V2_Q02';

-- Keep the established V2 keys stable; make room for the two new questions.
UPDATE questions SET display_order = display_order + 1
WHERE version_number = 2 AND display_order >= 13
  AND NOT EXISTS (
    SELECT 1 FROM (SELECT question_key, version_number FROM questions) existing
    WHERE existing.version_number = 2 AND existing.question_key = 'V2_Q11_CYCLES'
  );

INSERT INTO questions
  (question_key, version_number, display_order, section, question, `option`,
   response_type, input_type, is_required, min_value, max_value, step_value,
   placeholder, video_url, other_option_id, other_placeholder,
   parent_question_id, trigger_answer)
SELECT
  'V2_Q11_CYCLES', 2, 13, q.section,
  'Are your menstrual cycles regular?', NULL,
  'option', 'radio', 1, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
  q.id, 'Pre-menopausal'
FROM questions q
WHERE q.version_number = 2 AND q.question_key = 'V2_Q11'
  AND NOT EXISTS (
    SELECT 1 FROM questions x
    WHERE x.version_number = 2 AND x.question_key = 'V2_Q11_CYCLES'
  );

-- If the migration is re-run, enforce the intended configuration without
-- duplicating the row.
UPDATE questions child
JOIN questions parent
  ON parent.version_number = 2 AND parent.question_key = 'V2_Q11'
SET child.display_order = 13,
    child.question = 'Are your menstrual cycles regular?',
    child.response_type = 'option', child.input_type = 'radio',
    child.is_required = 1, child.parent_question_id = parent.id,
    child.trigger_answer = 'Pre-menopausal'
WHERE child.version_number = 2 AND child.question_key = 'V2_Q11_CYCLES';

INSERT INTO question_options (question_id, option_value, sort_order)
SELECT q.id, choices.option_value, choices.sort_order
FROM questions q
JOIN (
  SELECT 'Yes' AS option_value, 0 AS sort_order
  UNION ALL SELECT 'No', 1
) choices
WHERE q.version_number = 2 AND q.question_key = 'V2_Q11_CYCLES'
  AND NOT EXISTS (
    SELECT 1 FROM question_options qo
    WHERE qo.question_id = q.id AND qo.option_value = choices.option_value
  );

-- Menopause/surgery age remains conditional on the three non-pre-menopausal
-- statuses and follows the new menstrual-cycle question.
UPDATE questions
SET display_order = 14,
    question = 'If you answered ''Post-menopausal'', ''Post-hysterectomy'', or ''Post-oophorectomy'', at what age did you attain menopause or undergo the surgery?',
    trigger_answer = 'Post-menopausal | Post-hysterectomy | Post-oophorectomy'
WHERE version_number = 2 AND question_key = 'V2_Q11B';

-- Make room for age at first childbirth while preserving all existing keys.
UPDATE questions SET display_order = display_order + 1
WHERE version_number = 2 AND display_order >= 17
  AND NOT EXISTS (
    SELECT 1 FROM (SELECT question_key, version_number FROM questions) existing
    WHERE existing.version_number = 2 AND existing.question_key = 'V2_Q13_AGE_FIRST_BIRTH'
  );

INSERT INTO questions
  (question_key, version_number, display_order, section, question, `option`,
   response_type, input_type, is_required, min_value, max_value, step_value,
   placeholder, video_url, other_option_id, other_placeholder,
   parent_question_id, trigger_answer)
SELECT
  'V2_Q13_AGE_FIRST_BIRTH', 2, 17, q.section,
  'Please select your age at first child birth?', NULL,
  'option', 'radio', 1, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
  q.id, 'Yes'
FROM questions q
WHERE q.version_number = 2 AND q.question_key = 'V2_Q13'
  AND NOT EXISTS (
    SELECT 1 FROM questions x
    WHERE x.version_number = 2 AND x.question_key = 'V2_Q13_AGE_FIRST_BIRTH'
  );

UPDATE questions child
JOIN questions parent
  ON parent.version_number = 2 AND parent.question_key = 'V2_Q13'
SET child.display_order = 17,
    child.question = 'Please select your age at first child birth?',
    child.response_type = 'option', child.input_type = 'radio',
    child.is_required = 1, child.parent_question_id = parent.id,
    child.trigger_answer = 'Yes'
WHERE child.version_number = 2 AND child.question_key = 'V2_Q13_AGE_FIRST_BIRTH';

INSERT INTO question_options (question_id, option_value, sort_order)
SELECT q.id, choices.option_value, choices.sort_order
FROM questions q
JOIN (
  SELECT 'Less than 25' AS option_value, 0 AS sort_order
  UNION ALL SELECT '25 to 29', 1
  UNION ALL SELECT 'After 30', 2
) choices
WHERE q.version_number = 2 AND q.question_key = 'V2_Q13_AGE_FIRST_BIRTH'
  AND NOT EXISTS (
    SELECT 1 FROM question_options qo
    WHERE qo.question_id = q.id AND qo.option_value = choices.option_value
  );

-- Normalize the requested Q13 wording. Existing stable keys continue to be
-- used when saving responses and mapping the model features.
UPDATE questions SET question = 'Have you given birth to one or more children?', is_required = 1
WHERE version_number = 2 AND question_key = 'V2_Q13';
UPDATE questions SET question = 'How many times have you been pregnant in total? (Include all live births, miscarriages, stillbirths, and terminations)'
WHERE version_number = 2 AND question_key = 'V2_Q13A';
UPDATE questions SET question = 'Number of full-term pregnancies (>=37 weeks)'
WHERE version_number = 2 AND question_key = 'V2_Q13B';
UPDATE questions SET question = 'Number of miscarriages'
WHERE version_number = 2 AND question_key = 'V2_Q13C';
UPDATE questions SET question = 'Number of terminations'
WHERE version_number = 2 AND question_key = 'V2_Q13D';
UPDATE questions SET question = 'What is the total duration of breast feeding?', is_required = 1
WHERE version_number = 2 AND question_key = 'V2_Q13E';

-- Verification: expect 67 V2 questions, the two new questions once each,
-- the existing Biopsy option still present, and Version 1 still active.
SELECT version_number, version_name, is_active
FROM questionnaire_versions ORDER BY version_number;
SELECT question_key, display_order, question, input_type, is_required,
       parent_question_id, trigger_answer
FROM questions
WHERE version_number = 2
  AND question_key IN ('V2_Q02','V2_Q11','V2_Q11A','V2_Q11_CYCLES','V2_Q11B',
                       'V2_Q13','V2_Q13_AGE_FIRST_BIRTH','V2_Q13A','V2_Q13B',
                       'V2_Q13C','V2_Q13C_TRIMESTERS','V2_Q13D',
                       'V2_Q13D_TRIMESTERS','V2_Q13E')
ORDER BY display_order, id;
SELECT q.question_key, qo.option_value, qo.sort_order
FROM questions q JOIN question_options qo ON qo.question_id = q.id
WHERE q.version_number = 2
  AND q.question_key IN ('V2_Q11_CYCLES','V2_Q13_AGE_FIRST_BIRTH','V2_Q19B2')
ORDER BY q.question_key, qo.sort_order;
SELECT COUNT(*) AS v2_question_count FROM questions WHERE version_number = 2;

-- Deliberately no COMMIT. Run COMMIT only after reviewing the result grids.
