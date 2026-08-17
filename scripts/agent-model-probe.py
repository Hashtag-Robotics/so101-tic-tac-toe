"""Strands'in iki yapılandırılmış çıktı yolunu aynı model üstünde karşılaştırır.

A) Agent(structured_output_model=...) + agent(prompt)
   -> event loop sentetik bir araç yaratıp modeli onu çağırmaya zorluyor.
      Küçük yerel modeller araç çağrısında güvenilmez.

B) agent.structured_output(Model, prompt)
   -> sağlayıcının kendi structured_output'u. Ollama'da bu, isteğe
      `format: <json şeması>` koyuyor, yani üretim şemaya KISITLANIYOR.
      Model "araç çağırmayı becerecek" olmak zorunda değil.
"""

from __future__ import annotations

import os
import sys
import time
import warnings

sys.path.insert(0, "src")
os.environ.setdefault("HASHTAG_DATA_DIR", ".local-data")

from strands import Agent  # noqa: E402
from strands.models.ollama import OllamaModel  # noqa: E402

from hashtag_robotics.models import AgentPlan  # noqa: E402

MODEL = os.environ.get("DENEME_MODEL", "qwen2.5:3b")
OPTIONS = {"num_gpu": 0} if os.environ.get("CPU") else None

SYSTEM = "\n".join(
    [
        "You are a planning component inside Hashtag Robotics.",
        "Return one structured plan. A plan is an ordered list of steps.",
        "Available actions:",
        "- inspect_datasets: list the recordings",
        "- compare_datasets: can these be trained together? "
        "required: dataset_ids",
        "A parameter may read an earlier step with $<step>.<path>, '*' for each item.",
        'Example: {"dataset_ids": "$0.datasets.*.id"}',
    ]
)
PROMPT = "Which of my recordings can be trained together? Look at what I have, then compare."


def deneme(ad: str, calistir) -> None:
    print(f"\n--- {ad} ---")
    basla = time.monotonic()
    try:
        plan = calistir()
        sure = time.monotonic() - basla
        print(f"  BASARILI ({sure:.0f} s)")
        for index, step in enumerate(plan.steps):
            print(f"    {index}. {step.action}  {step.parameters}")
    except Exception as error:  # noqa: BLE001 - olcum araci
        sure = time.monotonic() - basla
        print(f"  DUSTU ({sure:.0f} s): {type(error).__name__}: {str(error)[:200]}")


def main() -> None:
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    print(f"model: {MODEL}   options: {OPTIONS}")

    def yol_a() -> AgentPlan:
        agent = Agent(
            model=OllamaModel("http://localhost:11434", model_id=MODEL, options=OPTIONS),
            system_prompt=SYSTEM,
            structured_output_model=AgentPlan,
            tools=[],
        )
        return agent(PROMPT).structured_output

    def yol_b() -> AgentPlan:
        agent = Agent(
            model=OllamaModel("http://localhost:11434", model_id=MODEL, options=OPTIONS),
            system_prompt=SYSTEM,
            tools=[],
        )
        return agent.structured_output(AgentPlan, PROMPT)

    deneme("A) structured_output_model (zorlanan arac cagrisi)", yol_a)
    deneme("B) agent.structured_output (saglayicinin sema kisiti)", yol_b)


if __name__ == "__main__":
    main()
