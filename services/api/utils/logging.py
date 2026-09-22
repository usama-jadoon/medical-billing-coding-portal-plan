import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class StructuredAuditLogger:
    """
    Structured logger that formats logs as JSON and strictly omits PHI fields.
    Never logs clinical notes, patient names, DOB, SSN, member ID, insurance ID,
    or document text content.
    """

    FORBIDDEN_KEYS = {
        "ssn", "dob", "patient_name", "first_name", "last_name",
        "member_id", "insurance_id", "clinical_note", "ocr_text",
        "quoted_text", "document_text", "prompt", "raw_content",
        "notes", "medical_record"
    }

    def __init__(self, name: str = "medical_coding_portal"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(logging.INFO)
            self.logger.addHandler(handler)
            self.logger.propagate = False

    def _sanitize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        sanitized = {}
        for k, v in data.items():
            if k.lower() in self.FORBIDDEN_KEYS:
                sanitized[k] = "[REDACTED_PHI]"
            elif isinstance(v, dict):
                sanitized[k] = self._sanitize(v)
            else:
                sanitized[k] = v
        return sanitized

    def log(
        self,
        level: str,
        action: str,
        request_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        status: Optional[str] = None,
        duration_ms: Optional[float] = None,
        error_code: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level.upper(),
            "action": action,
            "request_id": request_id,
            "actor_id": actor_id,
            "organization_id": organization_id,
            "status": status,
            "duration_ms": duration_ms,
            "error_code": error_code,
        }
        if metadata:
            payload["metadata"] = self._sanitize(metadata)

        # Filter out None keys for compactness
        filtered = {k: v for k, v in payload.items() if v is not None}
        message = json.dumps(filtered)
        if level.lower() == "error":
            self.logger.error(message)
        elif level.lower() == "warning":
            self.logger.warning(message)
        else:
            self.logger.info(message)


audit_logger = StructuredAuditLogger()
