"""MatchDay Ops — a GenAI real-time stadium operations & experience assistant
for the FIFA World Cup 2026.

Claude reasons about the *current* state of a match — crowd density, queues,
incidents, egress, accessibility — over grounded, cited tools, and answers
venue staff, volunteers, and fans in their own language. The facts come from
the tools; the model does the reasoning and the language handling.
"""

from .models import Answer, Persona
from .ops import MatchDayOps

__all__ = ["MatchDayOps", "Answer", "Persona"]
__version__ = "1.0.0"
