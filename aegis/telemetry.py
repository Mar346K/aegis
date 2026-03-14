import json
import logging
from datetime import datetime
from pathlib import Path

# Set up the audit log file in the root directory
LOG_FILE = Path("aegis-audit.log")

# Configure basic Python logging to write to the file
logger = logging.getLogger("AegisTelemetry")
logger.setLevel(logging.INFO)
handler = logging.FileHandler(LOG_FILE)
handler.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(handler)

def log_exfiltration_attempt(client_addr, destination="Unknown"):
    """
    Logs a blocked connection in a compliance-safe JSON format.
    Notice: We DO NOT log the payload or the secret to prevent data leakage.
    """
    audit_event = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event_type": "Data Exfiltration Prevented",
        "action": "BLOCKED",
        "source_ip": client_addr[0],
        "source_port": client_addr[1],
        "destination": destination,
        "reason": "Heuristic Engine: Critical Signature Match"
    }
    
    # Write the JSON string to the log file
    logger.info(json.dumps(audit_event))