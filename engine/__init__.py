"""Draft Intelligence Engine — probabilistic, evidence-traceable LoL draft recommendation system.

The numeric decision engine is fully functional without any LLM.
LLM (local Qwen) is used only for explanation and rule *proposals*, never as a
statistical source. See kutsal_amac.md for the governing specification.
"""

__version__ = "0.1.0"
SCHEMA_VERSION = "1.0"
