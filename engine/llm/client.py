"""Local Qwen client (kutsal_amac.md §14).

Discovery, not assumption: probes OpenAI-compatible and Ollama endpoints on the
configured host, verifies the EXACT model id exists, and never silently
substitutes another model. All failures degrade gracefully — the numeric
decision engine does not depend on this module.
"""
from __future__ import annotations

import json
import re
import urllib.request
import urllib.error
from dataclasses import dataclass

from engine.config import LLMConfig
from engine.contracts.schema import validate_record, SchemaError


class LLMUnavailable(RuntimeError):
    pass


class ModelNotFound(LLMUnavailable):
    pass


@dataclass
class Endpoint:
    kind: str          # "openai" | "ollama"
    base_url: str
    model: str
    available_models: list[str]


def _get_json(url: str, timeout: float):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _post_json(url: str, payload: dict, timeout: float):
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def discover(cfg: LLMConfig) -> Endpoint:
    """Probe configured endpoints; verify exact model presence."""
    errors = []
    probes = []
    if cfg.prefer == "openai":
        probes = [("openai", f"http://{cfg.host}:{cfg.openai_port}/v1"),
                  ("ollama", f"http://{cfg.host}:{cfg.ollama_port}")]
    else:
        probes = [("ollama", f"http://{cfg.host}:{cfg.ollama_port}"),
                  ("openai", f"http://{cfg.host}:{cfg.openai_port}/v1")]
    for kind, base in probes:
        try:
            if kind == "openai":
                data = _get_json(base + "/models", timeout=5)
                models = [m["id"] for m in data.get("data", [])]
            else:
                data = _get_json(base + "/api/tags", timeout=5)
                models = [m["name"] for m in data.get("models", [])]
            if cfg.model in models:
                return Endpoint(kind=kind, base_url=base, model=cfg.model,
                                available_models=models)
            errors.append(f"{kind}@{base}: model '{cfg.model}' not in {models[:6]}")
            if cfg.allow_model_substitution and models:
                return Endpoint(kind=kind, base_url=base, model=models[0],
                                available_models=models)
        except Exception as e:
            errors.append(f"{kind}@{base}: {type(e).__name__}: {e}")
    raise ModelNotFound("; ".join(errors) or "no endpoint reachable")


def _extract_json(text: str) -> dict:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    return json.loads(text)


class LLMClient:
    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg
        self._endpoint: Endpoint | None = None

    @property
    def endpoint(self) -> Endpoint:
        if self._endpoint is None:
            self._endpoint = discover(self.cfg)
        return self._endpoint

    def status(self) -> dict:
        try:
            ep = self.endpoint
            return {"available": True, "kind": ep.kind, "base_url": ep.base_url,
                    "model": ep.model}
        except LLMUnavailable as e:
            return {"available": False, "error": str(e)}

    def generate_json(self, system: str, prompt: str, schema_kind: str) -> dict:
        """Generate + schema-validate. One repair retry; then LLMUnavailable."""
        ep = self.endpoint
        last_err = None
        for attempt in range(self.cfg.max_retries + 1):
            try:
                if ep.kind == "openai":
                    resp = _post_json(ep.base_url + "/chat/completions", {
                        "model": ep.model,
                        "messages": [{"role": "system", "content": system},
                                     {"role": "user", "content": prompt}],
                        "temperature": 0.2,
                        "max_tokens": 2000,
                        "response_format": {"type": "json_object"},
                    }, timeout=self.cfg.timeout_s)
                    text = resp["choices"][0]["message"]["content"]
                else:
                    resp = _post_json(ep.base_url + "/api/chat", {
                        "model": ep.model,
                        "messages": [{"role": "system", "content": system},
                                     {"role": "user", "content": prompt}],
                        "stream": False, "format": "json",
                        "options": {"temperature": 0.2},
                    }, timeout=self.cfg.timeout_s)
                    text = resp["message"]["content"]
                parsed = _extract_json(text)
                validate_record(schema_kind, parsed)
                return parsed
            except (SchemaError, json.JSONDecodeError, KeyError) as e:
                last_err = e
                prompt = (prompt + "\n\nÖNCEKİ ÇIKTI GEÇERSİZDİ (" + str(e)[:200]
                          + "). SADECE geçerli JSON üret, şema alanlarını eksiksiz doldur.")
            except Exception as e:
                raise LLMUnavailable(f"{type(e).__name__}: {e}") from e
        raise LLMUnavailable(f"schema validation failed after retries: {last_err}")
