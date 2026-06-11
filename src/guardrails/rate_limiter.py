from collections import defaultdict, deque
import time
from google.adk.plugins import base_plugin
from google.genai import types

class RateLimitPlugin(base_plugin.BasePlugin):
    """Rate Limiter plugin to block users who send too many requests in a time window.
    Uses a sliding window based on timestamps.
    """
    def __init__(self, max_requests=10, window_seconds=60):
        super().__init__(name="rate_limiter")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.user_windows = defaultdict(deque)
        self.rate_limit_hits = 0

    async def on_user_message_callback(self, *, invocation_context, user_message):
        # Determine the user ID (default to 'student' if none provided)
        user_id = "anonymous"
        if invocation_context and hasattr(invocation_context, "user_id") and invocation_context.user_id:
            user_id = invocation_context.user_id
            
        now = time.time()
        window = self.user_windows[user_id]
        
        # Remove expired timestamps (older than the window size)
        while window and now - window[0] > self.window_seconds:
            window.popleft()
            
        # Check if the user has reached the request limit
        if len(window) >= self.max_requests:
            self.rate_limit_hits += 1
            wait_time = int(self.window_seconds - (now - window[0]))
            block_msg = f"Blocked: Rate limit exceeded. Please wait {wait_time} seconds before trying again."
            
            # Log the block in audit_logger
            from guardrails.audit_log import audit_logger
            request_id = id(invocation_context) if invocation_context else 0
            if request_id:
                audit_logger.log_blocked(request_id, "rate_limiter", block_msg)
                
            # Return a blocked content response immediately to stop pipeline execution
            return types.Content(
                role="model",
                parts=[
                    types.Part.from_text(text=block_msg)
                ]
            )
            
        # Otherwise, log the timestamp and allow the request
        window.append(now)
        return None
