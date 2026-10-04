import hashlib
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

def hash_user_id(user_id: str) -> str:
    """
    Creates a SHA-256 hash of a user ID to allow tracking of unique
    entities without exposing their real identifiers.
    """
    return hashlib.sha256(user_id.encode('utf-8')).hexdigest()
