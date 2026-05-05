class SecurityValidator:
    @staticmethod
    def safe_input_check(text: str) -> bool:
        """危险关键词过滤"""
        danger = ["drop", "delete", "rm -rf", "system", "exec"]
        for d in danger:
            if d in text.lower():
                return False
        return True

security = SecurityValidator()