import logging
from datetime import datetime
import json
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class AlertManager:
    def __init__(self, log_dir: str = '../data/realtime/alerts'):
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)
        self.alert_log_file = os.path.join(self.log_dir, 'active_alerts.jsonl')
        
    def trigger_alert(self, level: str, risk_score: float, context: dict):
        """
        Processes and dispatches an alert based on the severity level.
        :param level: Alert severity (LOW, MODERATE, HIGH, CRITICAL)
        :param risk_score: The numerical risk score
        :param context: Dictionary with additional context (e.g., Kp index, dB/dt)
        """
        alert_payload = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "risk_score": round(risk_score, 3),
            "context": context
        }
        
        self._log_alert_to_file(alert_payload)
        
        if level in ["HIGH", "CRITICAL"]:
            self._dispatch_critical_notification(alert_payload)
        elif level == "MODERATE":
            logging.info(f"MODERATE Risk Alert Logged. Score: {risk_score:.2f}")
            
    def _log_alert_to_file(self, payload: dict):
        """Appends the alert payload to a JSONL file."""
        try:
            with open(self.alert_log_file, 'a') as f:
                f.write(json.dumps(payload) + '\n')
        except Exception as e:
            logging.error(f"Failed to write alert to file: {e}")
            
    def _dispatch_critical_notification(self, payload: dict):
        """
        Placeholder for external notifications (e.g., MQTT, Email, SMS).
        For now, prints a highly visible warning to the console.
        """
        level = payload.get('level')
        score = payload.get('risk_score')
        
        logging.warning(f"!!! {level} GEOMAGNETIC RISK ALERT !!!")
        logging.warning(f"Risk Score: {score}")
        logging.warning(f"Context: {json.dumps(payload.get('context'), indent=2)}")
        
        # Here we would integrate paho-mqtt or sendgrid for real-world deployment

if __name__ == "__main__":
    # Test the Alert Manager
    manager = AlertManager(log_dir='./test_alerts')
    
    manager.trigger_alert(
        level="CRITICAL",
        risk_score=0.85,
        context={
            "kp_index": 8.0,
            "max_db_dt_nt_s": 4.5,
            "impacted_region": "North America Grid"
        }
    )
