"""Short-lived, signed WebSocket authorization shared with the Railway bot."""
from itsdangerous import URLSafeTimedSerializer

SALT = "leea-chat-v1"


def issue(secret, tenant):
    return URLSafeTimedSerializer(secret, salt=SALT).dumps(tenant)