import re

def sanitize_text(text: str) -> str:
    """
    Sanitizes text to remove personally identifiable information (PII)
    such as explicit usernames or specific patterns before storing.
    """
    # Remove @mentions (Twitter style)
    sanitized = re.sub(r'@\w+', '[USUARIO_ANONIMIZADO]', text)

    # Further sanitization could be added here (emails, phones, etc.)
    return sanitized
