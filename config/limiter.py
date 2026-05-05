from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# 按IP限流：每分钟最多20次请求
limiter = Limiter(key_func=get_remote_address)
limiter.default_limits = ["20/minute"]

def register_limiter(app):
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)