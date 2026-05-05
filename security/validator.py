class SecurityValidator:
    @staticmethod
    def check_input(text: str) -> bool:
        danger_keywords = [
            "drop", "delete", "rm -rf", "system", "exec",
            "eval", "subprocess", "os.popen", "shutdown"
        ]
        for kw in danger_keywords:
            if kw in text.lower():
                return False
        return True

security = SecurityValidator()