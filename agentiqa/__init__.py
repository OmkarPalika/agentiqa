__version__ = "0.1.0"

# Shown in the report/leaderboard CTA. Set your email, or leave empty to hide the line.
# Override at runtime with the AGENTIQA_CONTACT env var.
import os as _os

CONTACT = _os.environ.get("AGENTIQA_CONTACT", "your-email@example.com")
