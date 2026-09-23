"""Generate Version 2 multilingual informed-consent SQL using local NLLB.

Machine-generated translations must be checked in the local UI before deployment.
"""
import json
import re
from pathlib import Path

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer


LANGUAGES = {
    "hi": "hin_Deva", "bn": "ben_Beng", "gu": "guj_Gujr",
    "kn": "kan_Knda", "ml": "mal_Mlym", "mr": "mar_Deva",
    "or": "ory_Orya", "pa": "pan_Guru", "ta": "tam_Taml",
    "te": "tel_Telu",
}
MODEL_PATH = Path("/home/tanuh/bcd_portal/.models/nllb-200-distilled-600M")
ROOT = Path(__file__).resolve().parent
CACHE_PATH = ROOT / "informed_consent_translation_cache.json"
OUTPUT_PATH = ROOT / "migrations/20260909_add_informed_consent_v2_multilingual.sql"

ENGLISH = {
    "title": "INFORMED CONSENT FORM",
    "projectDetails": {
        "projectTitle": {"label": "Title of Project", "value": "AI Enabled Breast Cancer Risk Prediction Tool"},
        "iecReference": {"label": "IEC Reference Number", "value": "Clinicom vide letter no: 02434 dated 13-Jan-2026"},
        "iecApprovalDate": {"label": "IEC Approval Date", "value": "13-Jan-2026"},
        "iecApprovalDuration": {"label": "IEC Approval Duration", "value": "Until Mar 2028"},
    },
    "sections": [
        {
            "heading": "Voluntary Participation",
            "paragraphs": [{"text": "Your participation in this study is voluntary. You may refuse to participate in this study or in any part of this study at any time. Likewise the investigator also retains the right to terminate your participation in the experiment at any time without giving a reason. The decision to withdraw or terminate your participation will not affect your relations with your institute/university/hospital or affect the care you receive. You are encouraged to ask questions about this study any time during the study."}],
        },
        {
            "heading": "Information collected as part of this study",
            "paragraphs": [
                {"text": "Demographics, lifestyle, family history, menstrual and reproductive health information - necessary"},
                {"text": "Mammograms along with report (necessary)"},
                {"text": "ultrasound and/or biopsy report (optional)"},
            ],
        },
        {
            "heading": "Confidentiality and Data Protection",
            "paragraphs": [
                {"text": "Data Anonymization: All information gathered in this study will be collected, processed, and stored in an irreversibly anonymized manner to ensure your privacy. Collected information storage adheres to the Digital Personal Data Protection (DPDP) Act standards."},
                {"text": "The data collected will be used in future research, including the development of other foundation models."},
                {"text": "Rights: You have the right to access and correct your personal data and to withdraw your consent for research processing at any time. The decision to withdraw will not affect the regular clinical care you receive."},
                {"text": "Retention: Your irreversibly anonymized data and samples may be stored for as long as they are useful for lawful research and required safeguards are in place, in accordance with the DPDP Act and other legal or regulatory obligations."},
                {"text": "If you wish to speak to someone independent of the study as well as withdrawal of the consent, you may contact the Institutional Ethics Committee (IEC)"},
                {"text": "Name: Dr. Sri Vidya Jagadish, Secretary, IEC, TANUH"},
                {"text": "Email: secretary.iec@tanuh.ai"},
                {"text": "Phone# 080 - 2293 4106 / 2293 4107"},
            ],
        },
    ],
    "participantConsentHeading": "Participant Consent",
    "declaration": "I have read and understood the participation information sheet and confirmed to participate in this study voluntarily. I have had the opportunity to ask questions, and all my questions have been answered to my satisfaction. I understand that I have the right to withdraw my consent and refuse to participate at any time. I give my consent to be part of this study.",
    "ageCheckboxLabel": "I am 18 years of age or older",
    "voluntaryCheckboxLabel": "The information needed for this study is being provided voluntarily",
}


def strings(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from strings(child)
    elif isinstance(value, str):
        yield value


def preserve_verbatim(value):
    # Preserve only operational identifiers/contact details. Sentences such as
    # "I am 18 years of age or older" must still be translated.
    return (
        "@" in value
        or value.startswith("Phone#")
        or value.startswith("Clinicom vide letter no:")
        or bool(re.fullmatch(r"\d{1,2}-[A-Za-z]{3}-\d{4}", value))
    )


def replace_strings(value, mapping):
    if isinstance(value, dict):
        return {key: replace_strings(child, mapping) for key, child in value.items()}
    if isinstance(value, list):
        return [replace_strings(child, mapping) for child in value]
    if isinstance(value, str):
        return mapping.get(value, value)
    return value


def sql_quote(value):
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


def main():
    source_strings = list(dict.fromkeys(strings(ENGLISH)))
    cache = json.loads(CACHE_PATH.read_text(encoding="utf-8")) if CACHE_PATH.exists() else {}
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, src_lang="eng_Latn")
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_PATH)
    model.eval()

    translated_content = {"en": ENGLISH}
    for language, target_language in LANGUAGES.items():
        mapping = {}
        pending = []
        for source in source_strings:
            cache_key = f"{language}\t{source}"
            if preserve_verbatim(source):
                mapping[source] = source
            elif cache_key in cache:
                mapping[source] = cache[cache_key]
            else:
                pending.append(source)

        for offset in range(0, len(pending), 8):
            batch = pending[offset:offset + 8]
            inputs = tokenizer(batch, return_tensors="pt", padding=True, truncation=True, max_length=512)
            with torch.no_grad():
                tokens = model.generate(
                    **inputs,
                    forced_bos_token_id=tokenizer.convert_tokens_to_ids(target_language),
                    max_length=768,
                )
            translations = tokenizer.batch_decode(tokens, skip_special_tokens=True)
            for source, translated in zip(batch, translations):
                cache_key = f"{language}\t{source}"
                mapping[source] = translated
                cache[cache_key] = translated
            CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        translated_content[language] = replace_strings(ENGLISH, mapping)
        print(f"translated {language}")

    lines = [
        "-- Add informed-consent content to all Version 2 language rows.",
        "-- Review the verification SELECT, then explicitly COMMIT; or ROLLBACK;.",
        "SET NAMES utf8mb4;",
        "USE bcd_application2;",
        "START TRANSACTION;",
        "",
    ]
    for language, content in translated_content.items():
        payload = json.dumps(content, ensure_ascii=False, separators=(",", ":"))
        lines.append(
            "UPDATE participant_information_translations "
            f"SET content_json=JSON_SET(content_json, '$.informedConsent', CAST({sql_quote(payload)} AS JSON)), "
            "updated_at=CURRENT_TIMESTAMP "
            f"WHERE version_number=2 AND language_code={sql_quote(language)};"
        )
    lines.extend([
        "",
        "SELECT language_code,",
        "       JSON_UNQUOTE(JSON_EXTRACT(content_json, '$.informedConsent.title')) AS consent_title,",
        "       JSON_LENGTH(JSON_EXTRACT(content_json, '$.informedConsent.sections')) AS section_count,",
        "       JSON_UNQUOTE(JSON_EXTRACT(content_json, '$.informedConsent.ageCheckboxLabel')) AS age_confirmation",
        "FROM participant_information_translations",
        "WHERE version_number=2",
        "ORDER BY language_code;",
        "-- Deliberately no COMMIT.",
    ])
    OUTPUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"generated {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
