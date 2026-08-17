"""Elle yazılmış bir planı gerçek veri üstünde koşturur.

Planlayıcı modeli olmadan zincirin çalıştığını göstermenin yolu: modelin
üreteceği yapıyı elle kurup aynı çalıştırıcıya vermek. Model katmanı atlanıyor,
altındaki her şey gerçek -- gerçek veri seti tablosu, gerçek gateway, gerçek
kapı kontrolü.
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, "src")
os.environ.setdefault("HASHTAG_DATA_DIR", ".local-data")

from hashtag_robotics.agents import ROLE_PERMISSIONS  # noqa: E402
from hashtag_robotics.api import Runtime  # noqa: E402
from hashtag_robotics.config import get_settings  # noqa: E402
from hashtag_robotics.models import AgentPlan, AgentPlanStep  # noqa: E402
from hashtag_robotics.strands_runtime import execute_plan  # noqa: E402

PLAN = AgentPlan(
    rationale="Elimdeki kayıtların birlikte eğitilip eğitilemeyeceğini öğren.",
    steps=[
        AgentPlanStep(action="inspect_datasets", rationale="Önce ne var bakalım."),
        AgentPlanStep(
            action="compare_datasets",
            rationale="Bulduklarını birlikte eğitilebilir mi diye sor.",
            parameters={"dataset_ids": "$0.datasets.*.id"},
        ),
        AgentPlanStep(
            action="publish_dataset",
            rationale="Sonucu Hub'a gönder.",
            parameters={"dataset_id": "dataset_cotrain_real"},
        ),
    ],
)

DURUM = {
    "planned": "çalıştırılmadı",
    "completed": "TAMAM",
    "blocked": "engellendi",
    "failed": "başarısız",
    "awaiting_human": "İNSAN ONAYI BEKLİYOR",
    "skipped": "atlandı",
}


async def main() -> None:
    runtime = Runtime(get_settings())
    steps, stopped = await execute_plan(
        PLAN,
        "agent_dataset_curator",
        runtime.agents,
        set(ROLE_PERMISSIONS["dataset_curator"]),
    )

    print(f"\nPLAN: {PLAN.rationale}\n")
    for step in steps:
        print(f"  {step.index + 1}. {step.action:<22} {DURUM.get(step.state, step.state)}")
        print(f"      {step.message}")
        data = (step.command_result.data if step.command_result else {}) or {}
        if step.action == "inspect_datasets" and data.get("datasets"):
            names = [item["name"] for item in data["datasets"]]
            print(f"      -> {len(names)} kayıt buldu: {', '.join(names[:3])} ...")
        if step.action == "compare_datasets" and data.get("total_episodes") is not None:
            print(
                f"      -> {data['total_episodes']} bölüm / {data['total_frames']} kare, "
                f"durum: {data['status']}, engel: {len(data['blockers'])}"
            )
        for warning in step.warnings:
            print(f"      uyarı: {warning}")
    print(f"\nDURUŞ SEBEBİ: {stopped}\n")


if __name__ == "__main__":
    asyncio.run(main())
