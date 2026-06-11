import json
import time
from datetime import datetime
from google.adk.plugins import base_plugin
from google.genai import types

class AuditLogger:
    """Manages audit logging for all incoming user queries and LLM responses.
    Captures input, output, blocking safety layer, and roundtrip latency.
    """
    def __init__(self):
        self.logs = []
        self.active_requests = {}  # request_id -> request data

    def start_request(self, request_id, input_text):
        self.active_requests[request_id] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "input": input_text,
            "start_time": time.time(),
            "blocked": False,
            "blocked_by": None,
            "latency_ms": 0,
            "output": None
        }

    def log_blocked(self, request_id, blocked_by, output_text):
        if request_id in self.active_requests:
            req = self.active_requests[request_id]
            req["blocked"] = True
            req["blocked_by"] = blocked_by
            req["output"] = output_text
            req["latency_ms"] = int((time.time() - req["start_time"]) * 1000)
            self.logs.append(req)
            del self.active_requests[request_id]

    def log_success(self, request_id, output_text, blocked=False, blocked_by=None):
        if request_id in self.active_requests:
            req = self.active_requests[request_id]
            req["blocked"] = blocked
            req["blocked_by"] = blocked_by
            req["output"] = output_text
            req["latency_ms"] = int((time.time() - req["start_time"]) * 1000)
            self.logs.append(req)
            del self.active_requests[request_id]

    def export_json(self, filepath="security_audit.json"):
        # Flush any remaining active requests as successful/incomplete
        for req_id, req in list(self.active_requests.items()):
            req["latency_ms"] = int((time.time() - req["start_time"]) * 1000)
            self.logs.append(req)
            del self.active_requests[req_id]
            
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.logs, f, indent=2, ensure_ascii=False)
        print(f"Audit logs successfully exported to {filepath}")

# Global singleton logger instance
audit_logger = AuditLogger()


class AuditLogPlugin(base_plugin.BasePlugin):
    """ADK Plugin to start audit records and log safe request outputs."""
    def __init__(self):
        super().__init__(name="audit_log")

    async def on_user_message_callback(self, *, invocation_context, user_message):
        text = ""
        if user_message and user_message.parts:
            for part in user_message.parts:
                if hasattr(part, "text") and part.text:
                    text += part.text
                    
        request_id = id(invocation_context)
        audit_logger.start_request(request_id, text)
        return None

    async def after_model_callback(self, *, callback_context, llm_response):
        text = ""
        if hasattr(llm_response, "content") and llm_response.content:
            for part in llm_response.content.parts:
                if hasattr(part, "text") and part.text:
                    text += part.text
                    
        request_id = id(callback_context.invocation_context) if hasattr(callback_context, "invocation_context") else id(callback_context)
        
        # Check if output has been blocked or redacted by upstream output plugins
        blocked = False
        blocked_by = None
        if "apologize, but i cannot answer" in text.lower() or "safety restrictions" in text.lower():
            blocked = True
            blocked_by = "output_safety_judge"
        elif "[redacted]" in text.lower():
            blocked = False  # Redacted, but response still delivered
            blocked_by = "output_redaction"
            
        audit_logger.log_success(request_id, text, blocked=blocked, blocked_by=blocked_by)
        return llm_response
