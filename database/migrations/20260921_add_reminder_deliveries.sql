-- Recipient-specific cycles; legacy reminder_email_log is retained for history/cadence.
CREATE TABLE IF NOT EXISTS reminder_deliveries (
    id INT AUTO_INCREMENT PRIMARY KEY,
    scope VARCHAR(80) NOT NULL,
    recipient_email VARCHAR(255) NOT NULL,
    cycle_date DATE NOT NULL,
    subject VARCHAR(255) NOT NULL,
    body_html MEDIUMTEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    attempts INT NOT NULL DEFAULT 0,
    last_attempt_date DATE NULL,
    sent_at DATETIME NULL,
    error_message TEXT NULL,
    alert_sent_at DATETIME NULL,
    CONSTRAINT uq_reminder_delivery_cycle UNIQUE (scope, recipient_email, cycle_date)
);
