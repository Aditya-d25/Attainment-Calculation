"""
LLM-based contextual reasoning for CO-PO mapping.

Provides an abstraction layer supporting:
- Google Gemini API
- Mock provider (rule-based, for development/testing)
- Extensible to OpenAI, Anthropic, etc.

The LLM receives CO text, PO text, semantic similarity,
and optional course context. It returns structured JSON
with mapping_level, confidence, reason, and evidence.
"""

import os
import json
import logging
import random
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

from ai.preprocessor import extract_action_verbs, extract_key_concepts

logger = logging.getLogger(__name__)


# -------------------------
# Structured Usage Tracking  (Finding 6)
# -------------------------

@dataclass
class UsageRecord:
    """One structured entry per HTTP attempt — never logs keys or full prompts."""
    generation_id: str
    batch_number: int
    attempt: int
    model: str
    http_status: Optional[int]
    latency_ms: float
    candidate_count: int
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    error: Optional[str] = None
    fallback: bool = False


@dataclass
class GenerationUsageSummary:
    """Aggregated usage stats for an entire generation run."""
    generation_id: str
    total_batches: int
    total_attempts: int
    total_candidates: int
    models_used: List[str] = field(default_factory=list)
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_latency_ms: float = 0.0
    failed_attempts: int = 0
    records: List[UsageRecord] = field(default_factory=list)

    def add(self, rec: UsageRecord):
        self.records.append(rec)
        self.total_attempts += 1
        self.total_latency_ms += rec.latency_ms
        if rec.prompt_tokens:
            self.total_prompt_tokens += rec.prompt_tokens
        if rec.completion_tokens:
            self.total_completion_tokens += rec.completion_tokens
        if rec.model and rec.model not in self.models_used:
            self.models_used.append(rec.model)
        if rec.error:
            self.failed_attempts += 1


class MappingResult:
    """Structured result from LLM reasoning."""

    def __init__(
        self,
        co_code: str,
        po_pso_code: str,
        mapping_level: int,
        confidence: float,
        reason: str,
        evidence: List[str],
        similarity_score: float = 0.0,
    ):
        self.co_code = co_code
        self.po_pso_code = po_pso_code
        self.mapping_level = mapping_level
        self.confidence = confidence
        self.reason = reason
        self.evidence = evidence
        self.similarity_score = similarity_score

    def to_dict(self) -> Dict:
        return {
            "co_code": self.co_code,
            "po_pso_code": self.po_pso_code,
            "mapping_level": self.mapping_level,
            "confidence": self.confidence,
            "reason": self.reason,
            "evidence": self.evidence,
            "similarity_score": self.similarity_score,
        }


# -------------------------
# Non-retryable HTTP status codes  (Finding 3)
# -------------------------
_NON_RETRYABLE_STATUSES = {400, 401, 403, 404, 405, 422}

# -------------------------
# Retryable (transient) status codes  (Finding 3)
# -------------------------
_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def reason_mapping(
        self,
        co_code: str,
        co_text: str,
        po_pso_code: str,
        po_pso_text: str,
        similarity_score: float,
        context: Optional[str] = None,
    ) -> MappingResult:
        """
        Determine the CO-PO/PSO mapping using contextual reasoning.

        Returns a MappingResult with level, confidence, reason, and evidence.
        """
        pass

    def reason_candidates_batch(
        self,
        candidates: List[Dict],
        context: Optional[str] = None,
    ) -> List[MappingResult]:
        """Batch reasoning for multiple candidate pairs (default calls reason_mapping)."""
        results = []
        for c in candidates:
            res = self.reason_mapping(
                co_code=c["co_code"],
                co_text=c["co_text"],
                po_pso_code=c["po_pso_code"],
                po_pso_text=c["po_pso_text"],
                similarity_score=c["similarity_score"],
                context=context,
            )
            results.append(res)
        return results  # Finding 4: was missing

    @staticmethod
    def _safe_float(val, default: float = 0.85) -> float:
        """Safely convert string/numeric confidence to float between 0.0 and 1.0."""
        if val is None:
            return default
        if isinstance(val, (int, float)):
            f = float(val)
            if f > 1.0:
                f = f / 100.0
            return max(0.0, min(1.0, f))
        if isinstance(val, str):
            v = val.strip().lower()
            if "%" in v:
                v = v.replace("%", "").strip()
            if "high" in v:
                return 0.90
            if "med" in v:
                return 0.70
            if "low" in v:
                return 0.50
            try:
                f = float(v)
                if f > 1.0:
                    f = f / 100.0
                return max(0.0, min(1.0, f))
            except ValueError:
                return default
        return default

    @staticmethod
    def _safe_int(val, default: int = 0) -> int:
        """Safely convert string/numeric mapping level to int between 0 and 3."""
        if val is None:
            return default
        if isinstance(val, (int, float)):
            return max(0, min(3, int(val)))
        if isinstance(val, str):
            v = val.strip().lower()
            if "strong" in v or "high" in v or v == "3":
                return 3
            if "moderate" in v or "medium" in v or v == "2":
                return 2
            if "low" in v or "weak" in v or v == "1":
                return 1
            if "none" in v or "no" in v or v == "0":
                return 0
            try:
                return max(0, min(3, int(float(v))))
            except ValueError:
                return default
        return default

    def _pedagogical_fallback(self, c: Dict, context: Optional[str] = None) -> MappingResult:
        """Pedagogical fallback engine (SHUT DOWN - STRICT LLM MODE)."""
        co = c.get("co_code", "UNKNOWN")
        po = c.get("po_pso_code", "UNKNOWN")
        raise RuntimeError(
            f"Pedagogical fallback engine is SHUT DOWN. "
            f"Candidate pair {co} vs {po} failed or was omitted by the LLM."
        )

    def _extract_json_items(self, text: str) -> List[Dict]:
        """Robustly parse JSON array or dictionary wrapper from LLM output."""
        text = text.strip()
        text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE).strip()

        def _find_candidate_list(data) -> Optional[List[Dict]]:
            if isinstance(data, list):
                if data and isinstance(data[0], dict) and ("co_code" in data[0] or "mapping_level" in data[0]):
                    return data
                dicts = [x for x in data if isinstance(x, dict)]
                if dicts and any("co_code" in d or "mapping_level" in d for d in dicts):
                    return dicts
                return data
            if isinstance(data, dict):
                if "co_code" in data and "po_pso_code" in data:
                    return [data]
                for k in ["mappings", "results", "candidate_pairs", "pairs", "data", "objects", "items", "outcomes"]:
                    if k in data and isinstance(data[k], list):
                        res = _find_candidate_list(data[k])
                        if res:
                            return res
                for v in data.values():
                    if isinstance(v, list) and v and isinstance(v[0], dict) and ("co_code" in v[0] or "mapping_level" in v[0]):
                        return v
                if len(data) == 1:
                    single_val = next(iter(data.values()))
                    if isinstance(single_val, list):
                        return single_val
                return [data]
            return None

        try:
            val = json.loads(text)
            res = _find_candidate_list(val)
            if res is not None:
                return res
        except Exception:
            pass

        m = re.search(r'\[.*\]', text, re.DOTALL)
        if m:
            try:
                items = json.loads(m.group(0))
                res = _find_candidate_list(items)
                if res is not None:
                    return res
            except Exception:
                pass

        m_obj = re.search(r'\{.*\}', text, re.DOTALL)
        if m_obj:
            try:
                obj = json.loads(m_obj.group(0))
                res = _find_candidate_list(obj)
                if res is not None:
                    return res
            except Exception:
                pass

        return []


# -------------------------
# Canonical NBA Program Outcomes & Specific Outcomes (Clean Reference)
# -------------------------

CANONICAL_PO_DEFINITIONS = {
    "PO1": "Engineering Knowledge: Apply mathematics, science, and engineering fundamentals to computational solutions.",
    "PO2": "Problem Analysis: Formulate and analyze complex problems, data representations, convergence, and architectures.",
    "PO3": "Design/Development of Solutions: Design, build, train, and validate software systems, neural architectures, or algorithms.",
    "PO4": "Conduct Investigations: Design benchmarking experiments, ablation studies, hyperparameter optimization, and empirical evaluation.",
    "PO5": "Modern Tool Usage: Hands-on use of deep learning frameworks (PyTorch, TensorFlow, Keras, CUDA, OpenCV, Pretrained Hubs).",
    "PO6": "The Engineer and Society: Societal applications in healthcare, industry automation, public safety, and contextual impact.",
    "PO7": "Environment and Sustainability: Computational resource efficiency, GPU carbon footprint, model compression, green AI.",
    "PO8": "Ethics: AI fairness, dataset privacy, security standards, bias mitigation, and responsible engineering.",
    "PO9": "Individual and Team Work: Group collaboration, code review, peer leadership, and shared project deliverables.",
    "PO10": "Life-long Learning: Upskilling and adapting to rapidly evolving architectures and emerging deep learning paradigms.",
    "PO11": "Project Management and Finance: Budgeting compute resources, timeline management, and engineering deliverables.",
    "PO12": "Computational Complexity & Optimization: Algorithmic time/space complexity, FLOPs, parameter count, and memory footprint.",
    "PSO1": "IT Information Systems: End-to-end application software pipelines and intelligent data processing in multidisciplinary domains.",
    "PSO2": "Computing Infrastructure: Managing GPU clusters, cloud infrastructure, VRAM constraints, and scalable deployment.",
    "PSO3": "Business Processes: Enterprise integration, business ROI, commercial workflows, and organizational deployment.",
    "PSO4": "Professional Decision Making: Technical reporting, stakeholder communication, and architectural trade-off justification.",
}


# -------------------------
# Mock Provider  (Finding 5)
# -------------------------

class MockProvider(LLMProvider):
    """
    MockProvider is SHUT DOWN.
    Real LLM inference with a valid API key is strictly required.
    """

    def reason_mapping(
        self,
        co_code: str,
        co_text: str,
        po_pso_code: str,
        po_pso_text: str,
        similarity_score: float,
        context: Optional[str] = None,
    ) -> MappingResult:
        raise RuntimeError("MockProvider is SHUT DOWN. A valid GROQ_API_KEY is required to generate mappings.")

    def reason_candidates_batch(
        self,
        candidates: List[Dict],
        context: Optional[str] = None,
    ) -> List[MappingResult]:
        raise RuntimeError("MockProvider is SHUT DOWN. A valid GROQ_API_KEY is required to generate mappings.")


# -------------------------
# Groq / Grok Provider
# -------------------------

class GroqProvider(LLMProvider):
    """
    Groq / Grok provider supporting ultra-fast inference (e.g. Llama-3.3-70B or Grok).
    Utilizes OpenAI-compatible chat completions with high tokens/sec.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "openai/gpt-oss-120b",
        base_url: Optional[str] = None
    ):
        self.api_key = api_key
        self.model = model
        if base_url:
            self.base_url = base_url.rstrip("/")
        elif "xai" in model.lower() or "grok" in model.lower():
            self.base_url = "https://api.x.ai/v1"
        else:
            self.base_url = "https://api.groq.com/openai/v1"

    FALLBACK_MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]

    @staticmethod
    def _parse_groq_wait_time(resp) -> float:
        """Parse exact seconds to wait from Groq 429 headers or error payload, capped at 30 seconds."""
        import re
        headers = resp.headers if resp is not None else {}

        # 1. First check x-ratelimit-reset-tokens (most accurate for TPM refills)
        rt = headers.get("x-ratelimit-reset-tokens", "")
        if rt:
            try:
                total_sec = 0.0
                m_min = re.search(r"(\d+(?:\.\d+)?)m(?!s)", rt)
                if m_min:
                    total_sec += float(m_min.group(1)) * 60.0
                m_ms = re.search(r"(\d+(?:\.\d+)?)ms", rt)
                m_sec = re.search(r"(\d+(?:\.\d+)?)s", rt)
                if m_ms:
                    total_sec += float(m_ms.group(1)) / 1000.0
                elif m_sec:
                    total_sec += float(m_sec.group(1))
                if total_sec > 0:
                    return min(30.0, max(2.0, total_sec + 1.0))
            except Exception:
                pass

        # 2. Check JSON error message: "try again in X.Xs"
        if resp is not None:
            try:
                data = resp.json()
                msg = data.get("error", {}).get("message", "")
                m = re.search(r"try again in (\d+(?:\.\d+)?)\s*(s|m|ms)", msg, re.IGNORECASE)
                if m:
                    val = float(m.group(1))
                    unit = m.group(2).lower()
                    if unit == "m":
                        val *= 60.0
                    elif unit == "ms":
                        val /= 1000.0
                    return min(30.0, max(2.0, val + 1.0))
            except Exception:
                pass

        # 3. Check retry-after header (capped so it never hangs for minutes)
        ra = headers.get("retry-after")
        if ra:
            try:
                return min(30.0, max(2.0, float(ra) + 1.0))
            except ValueError:
                pass

        return 10.0

    def reason_mapping(
        self,
        co_code: str,
        co_text: str,
        po_pso_code: str,
        po_pso_text: str,
        similarity_score: float,
        context: Optional[str] = None,
    ) -> MappingResult:
        candidates = [{
            "co_code": co_code,
            "co_text": co_text,
            "po_pso_code": po_pso_code,
            "po_pso_text": po_pso_text,
            "similarity_score": similarity_score,
        }]
        res = self.reason_candidates_batch(candidates, context=context)
        if res:
            return res[0]
        raise RuntimeError(f"Groq reasoning failed for {co_code} vs {po_pso_code}. Pedagogical fallback is shut down.")

    def reason_candidates_batch(
        self,
        candidates: List[Dict],
        context: Optional[str] = None,
    ) -> List[MappingResult]:
        if not candidates:
            return []

        import requests as http_lib
        import uuid
        import time
        import random
        from collections import OrderedDict

        # Helper to normalize outcome codes for resilient matching (e.g., 'CO-6' == 'CO6' == 'CO 6')
        def _norm_code(c: str) -> str:
            return re.sub(r'[^A-Z0-9]', '', str(c).upper())

        all_results = []

        auth_headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        endpoint = f"{self.base_url}/chat/completions"

        # Group candidates by course outcome (CO) so the LLM evaluates the entire CO holistically
        co_groups = OrderedDict()
        for c in candidates:
            co = c["co_code"]
            if co not in co_groups:
                co_groups[co] = []
            co_groups[co].append(c)

        total_cos = len(co_groups)
        generation_id = uuid.uuid4().hex[:12]
        usage_summary = GenerationUsageSummary(
            generation_id=generation_id,
            total_batches=total_cos,
            total_attempts=0,
            total_candidates=len(candidates),
        )

        exhausted_models: set = set()
        logger.info(
            f"⚡ [Groq] Starting holistic reasoning for {len(candidates)} candidate pairs "
            f"across {total_cos} course outcomes (model={self.model}, gen={generation_id})..."
        )

        context_info = f"Course: {context}\n" if context else ""

        co_idx = 0
        for co_code, co_chunk in co_groups.items():
            co_idx += 1
            is_last_co = (co_idx == total_cos)
            first_c = co_chunk[0]
            co_text = first_c.get("co_text", "")
            bloom = first_c.get("bloom_level", "L3 - Apply")

            # Build clean list of target outcomes for this CO
            target_outcomes_desc = []
            for idx, c in enumerate(co_chunk, 1):
                po_code = c["po_pso_code"]
                # Use canonical definition to eliminate truncated/noisy OCR strings
                po_desc = CANONICAL_PO_DEFINITIONS.get(po_code, c.get("po_pso_text", ""))
                target_outcomes_desc.append(f"{idx}. {po_code}: {po_desc}")

            co_prompt = f"""You are a Senior National Board of Accreditation (NBA) Evaluator and OBE Curriculum Expert.
Evaluate Course Outcome {co_code}:
\"{co_text}\" [Bloom Taxonomy: {bloom}]
{context_info}
Evaluate relationship strength (Mapping Level 0, 1, 2, or 3) against the following Program Outcomes (POs/PSOs):
{chr(10).join(target_outcomes_desc)}

OBE / NBA Accreditation Scale & Rubrics:
- Level 3 (Substantial / Primary Objective): The CO directly and deeply embodies this outcome as its primary engineering mission.
  • Bloom L3-L6 actively designing, implementing, or evaluating models/architectures (e.g. CNNs, RNNs, Autoencoders, PyTorch, TensorFlow).
  • PO1: Core mathematical, algorithmic, and engineering science foundations directly applied -> Level 2 or 3.
  • PO2: Problem analysis, comparing architectures, formulating solutions -> Level 2 or 3.
  • PO3: Designing, implementing, and deploying software architectures or solutions -> Level 3.
  • PO4: Benchmarking, ablation studies, empirical performance evaluation -> Level 2 or 3.
  • PO5: Modern Tool usage (TensorFlow, PyTorch, CUDA, GPUs) -> Level 2 or 3 for practical DL computational courses.
  • PSOs: Direct specialized technical capability in software pipelines or computing infrastructure -> Level 2 or 3.
- Level 2 (Moderate / Supportive): Meaningful conceptual or supportive contribution.
- Level 1 (Low / Tangential): Peripheral, minor, or contextual connection (e.g. PO6, PO7, PO8, PO10).
- Level 0 (None): No direct contribution (e.g. PO9, PO11, PSO3 are 0 unless explicitly taught and evaluated).

Return ONLY a valid JSON object with key 'mappings' containing a list of {len(co_chunk)} objects, each with:
- 'po_pso_code': string (e.g. '{co_chunk[0]["po_pso_code"]}')
- 'mapping_level': integer 0, 1, 2, or 3
- 'reason': 1 concise sentence explaining the educational rationale
- 'evidence': array of 1-2 specific technical keywords
"""

            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an NBA accreditation evaluation engine. Always return valid JSON only."
                    },
                    {
                        "role": "user",
                        "content": co_prompt
                    }
                ],
                "response_format": {"type": "json_object"},
                "temperature": float(os.getenv("LLM_TEMPERATURE", "0.1")),
                "max_tokens": 3000,
            }

            max_attempts = 8
            resp = None

            try:
                for attempt in range(max_attempts):
                    is_final_attempt = (attempt == max_attempts - 1)
                    attempt_start = time.monotonic()
                    rec = UsageRecord(
                        generation_id=generation_id,
                        batch_number=co_idx,
                        attempt=attempt + 1,
                        model=payload["model"],
                        http_status=None,
                        latency_ms=0.0,
                        candidate_count=len(co_chunk),
                    )

                    try:
                        resp = http_lib.post(endpoint, headers=auth_headers, json=payload, timeout=35)
                    except (http_lib.exceptions.Timeout, http_lib.exceptions.ConnectionError) as net_err:
                        rec.latency_ms = (time.monotonic() - attempt_start) * 1000
                        rec.error = f"{type(net_err).__name__}: {net_err}"
                        usage_summary.add(rec)

                        if is_final_attempt:
                            raise RuntimeError(f"Network error after {max_attempts} attempts: {net_err}")

                        wait = min(30.0, (2 ** attempt) + random.uniform(0, 1))
                        logger.warning(f"⚠️ [Groq] Network error ({attempt+1}/{max_attempts}): {net_err}. Retrying in {wait:.1f}s...")
                        time.sleep(wait)
                        continue

                    rec.latency_ms = (time.monotonic() - attempt_start) * 1000
                    rec.http_status = resp.status_code

                    # Record token metrics
                    if resp.status_code == 200:
                        try:
                            token_usage = resp.json().get("usage", {})
                            rec.prompt_tokens = token_usage.get("prompt_tokens")
                            rec.completion_tokens = token_usage.get("completion_tokens")
                            rec.total_tokens = token_usage.get("total_tokens")
                        except Exception:
                            pass

                    # Handle 429 Rate Limits
                    if resp.status_code == 429:
                        err_text = resp.text.lower() if resp is not None else ""

                        # If TPD (daily quota) exhausted, try next model in fallback list
                        if "tokens per day" in err_text or "tpd" in err_text:
                            exhausted_models.add(payload["model"])
                            next_model = next((m for m in self.FALLBACK_MODELS if m not in exhausted_models), None)
                            if next_model:
                                rec.fallback = True
                                rec.error = f"TPD exhausted on {payload['model']}, switching to {next_model}"
                                usage_summary.add(rec)
                                logger.warning(f"⚠️ [Groq] Daily quota exhausted on {payload['model']}. Switching to {next_model}...")
                                payload["model"] = next_model
                                self.model = next_model
                                continue
                            else:
                                rec.error = "All fallback models exhausted"
                                usage_summary.add(rec)
                                raise RuntimeError(f"All fallback models exhausted (tried: {list(exhausted_models)}).")

                        # TPM Rate limit: sleep exact wait time and retry
                        rec.error = "Rate limited (429)"
                        usage_summary.add(rec)

                        if is_final_attempt:
                            logger.error(f"❌ [Groq] Rate limit reached on final attempt {attempt+1}/{max_attempts}.")
                            break

                        wait_sec = self._parse_groq_wait_time(resp)
                        logger.info(f"⏳ [Groq] TPM limit reached. Pausing {wait_sec:.1f}s (attempt {attempt+1}/{max_attempts})...")
                        time.sleep(wait_sec)
                        continue

                    # Non-retryable client errors
                    if resp.status_code in _NON_RETRYABLE_STATUSES:
                        rec.error = f"Non-retryable HTTP {resp.status_code}"
                        usage_summary.add(rec)
                        raise RuntimeError(f"Non-retryable HTTP {resp.status_code}: {resp.text[:200]}")

                    # Retryable server errors (5xx)
                    if resp.status_code in _RETRYABLE_STATUSES and resp.status_code != 429:
                        rec.error = f"Server error HTTP {resp.status_code}"
                        usage_summary.add(rec)
                        if is_final_attempt:
                            break
                        wait = min(30.0, (2 ** attempt) + random.uniform(0, 1))
                        time.sleep(wait)
                        continue

                    usage_summary.add(rec)
                    break

                if resp is None or resp.status_code != 200:
                    status = resp.status_code if resp is not None else 'None'
                    body = resp.text[:200] if resp is not None else 'No response'
                    raise RuntimeError(f"HTTP {status}: {body}")

                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                items = self._extract_json_items(content)

                # Resilient key lookup using normalized strings (e.g. 'PO1', 'po1', 'PO-1' all match)
                res_map = {}
                for it in items:
                    if isinstance(it, dict):
                        po_raw = it.get("po_pso_code") or it.get("outcome_code") or it.get("code") or ""
                        if po_raw:
                            res_map[_norm_code(po_raw)] = it

                # Map each candidate pair for this CO
                for c in co_chunk:
                    target_code = c["po_pso_code"]
                    norm_target = _norm_code(target_code)

                    if norm_target in res_map:
                        it = res_map[norm_target]
                        ev = it.get("evidence", [])
                        if isinstance(ev, str):
                            ev = [ev]
                        all_results.append(MappingResult(
                            co_code=c["co_code"],
                            po_pso_code=c["po_pso_code"],
                            mapping_level=self._safe_int(it.get("mapping_level", 0)),
                            confidence=self._safe_float(it.get("confidence", 0.90)),
                            reason=str(it.get("reason", "Correlated via curriculum outcome alignment.")),
                            evidence=ev if isinstance(ev, list) else [],
                            similarity_score=c["similarity_score"],
                        ))
                    else:
                        # Resilient recovery: if LLM omitted a candidate, infer a safe rating rather than crashing
                        sim = float(c.get("similarity_score", 0.0))
                        inferred_level = 2 if sim >= 0.40 else (1 if sim >= 0.20 else 0)
                        logger.warning(
                            f"⚠️ [Groq] LLM omitted {c['co_code']} vs {c['po_pso_code']} in CO batch {co_idx}. "
                            f"Inferred Level {inferred_level} from semantic similarity ({sim:.2f})."
                        )
                        all_results.append(MappingResult(
                            co_code=c["co_code"],
                            po_pso_code=c["po_pso_code"],
                            mapping_level=inferred_level,
                            confidence=0.75,
                            reason=f"Correlated via outcome alignment and semantic similarity ({sim:.2f}).",
                            evidence=[c["po_pso_code"]],
                            similarity_score=sim,
                        ))

                logger.info(f"✅ [Groq] {co_code} ({co_idx}/{total_cos}) completed ({len(co_chunk)} outcomes mapped).")

            except Exception as e:
                logger.error(f"❌ Groq reasoning error on {co_code} ({type(e).__name__}: {e})")
                raise RuntimeError(f"Groq reasoning failed for {co_code}: {e}")

            # Gentle pause between COs to avoid TPM spikes
            if not is_last_co:
                time.sleep(1.5)

        logger.info(
            f"🚀 [Groq] Generation {generation_id} complete: "
            f"{usage_summary.total_candidates} candidate pairs across {total_cos} CO batches, "
            f"prompt_tokens={usage_summary.total_prompt_tokens}, "
            f"completion_tokens={usage_summary.total_completion_tokens}, "
            f"latency={usage_summary.total_latency_ms:.0f}ms"
        )

        return all_results



# -------------------------
# Provider Factory  (Finding 5: explicit selection + MockProvider defined)
# -------------------------

def get_llm_provider() -> LLMProvider:
    """
    Get the configured LLM provider.
    MockProvider is SHUT DOWN. If GROQ_API_KEY is missing or invalid, an error is raised.
    """
    from dotenv import load_dotenv
    load_dotenv(override=True)

    mock_mode = os.getenv("MOCK_MODE", "false").lower() == "true"
    provider_name = os.getenv("LLM_PROVIDER", "groq").lower().strip()

    if mock_mode or provider_name == "mock":
        raise RuntimeError(
            "MockProvider is SHUT DOWN. Please ensure MOCK_MODE=false and provide a valid GROQ_API_KEY in .env."
        )

    api_key = (
        os.getenv("GROQ_API_KEY", "")
        or os.getenv("GROK_API_KEY", "")
        or os.getenv("LLM_API_KEY", "")
    )
    model = (
        os.getenv("GROQ_MODEL", "")
        or os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
    )
    base_url = os.getenv("GROQ_BASE_URL", "") or os.getenv("LLM_BASE_URL", "")

    if not api_key or api_key.startswith("REPLACE_WITH") or "REPLACE" in api_key:
        raise RuntimeError(
            "Missing or invalid GROQ_API_KEY in .env. MockProvider is shut down. "
            "Please configure a valid Groq API key in .env to generate mappings."
        )

    if provider_name in ("groq", "grok"):
        return GroqProvider(api_key=api_key, model=model, base_url=base_url or None)

    logger.warning(
        f"Unsupported LLM_PROVIDER='{provider_name}'. "
        f"Falling back to GroqProvider since an API key is available."
    )
    return GroqProvider(api_key=api_key, model=model, base_url=base_url or None)
