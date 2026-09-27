"""
Generate Operational Dashboard Image from Measured Golden Signals & Telemetry
Business Case ID: BC-AAIE-HACK-06
"""

import os
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec


def generate_dashboard_image(
    dashboard_data_path: str = "reports/dashboard_data.json",
    output_png_path: str = "reports/dashboard.png"
):
    if not os.path.exists(dashboard_data_path):
        print(f"[DashboardGen] {dashboard_data_path} not found. Skipping image generation.")
        return

    with open(dashboard_data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    kpi = data.get("kpi_summary", {})
    lat = data.get("agent_latency_profile_ms", {})
    deepeval = data.get("deepeval_llm_judge_benchmark", {})
    meta = data.get("dashboard_metadata", {})

    fig = plt.figure(figsize=(14, 8), facecolor="#0f172a")
    gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.35, wspace=0.3)

    # 1. Header Banner
    ax_title = fig.add_axes([0.05, 0.92, 0.9, 0.06])
    ax_title.axis("off")
    ax_title.text(
        0.0, 0.6,
        "FNOL Claims-Triage Copilot | Operational Telemetry & Golden Signals",
        fontsize=16, fontweight="bold", color="#38bdf8", va="center"
    )
    ax_title.text(
        0.0, 0.1,
        f"Active Model: {meta.get('active_llm', 'gemini-3.5-flash-lite')}  |  Framework: {meta.get('framework', 'LangGraph + Stdio MCP')}  |  Timestamp: {meta.get('last_updated', 'Latest Run')[:19]}",
        fontsize=9, color="#94a3b8", va="center"
    )

    # 2. KPI Cards (Top Left)
    ax_kpi = fig.add_subplot(gs[0, 0])
    ax_kpi.set_facecolor("#1e293b")
    ax_kpi.axis("off")
    ax_kpi.text(0.08, 0.88, "GOLDEN SIGNALS SUMMARY", fontsize=11, fontweight="bold", color="#f8fafc")
    ax_kpi.text(0.08, 0.70, f"Total Spans: {kpi.get('total_spans_recorded', 0)}", fontsize=10, color="#cbd5e1")
    ax_kpi.text(0.08, 0.54, f"Tokens Consumed: {kpi.get('total_tokens_consumed', 0):,}", fontsize=10, color="#cbd5e1")
    ax_kpi.text(0.08, 0.38, f"Estimated Cost: ${kpi.get('estimated_cost_usd', 0.0):.6f}", fontsize=10, color="#34d399")
    ax_kpi.text(0.08, 0.22, f"Success Rate: {kpi.get('measured_success_rate', 1.0) * 100:.1f}%", fontsize=10, color="#38bdf8")
    ax_kpi.text(0.08, 0.06, f"Grounded Accuracy: {kpi.get('grounded_accuracy_score', 1.0) * 100:.1f}%", fontsize=10, color="#a78bfa")

    # 3. Latency Distribution (Top Center)
    ax_lat = fig.add_subplot(gs[0, 1])
    ax_lat.set_facecolor("#1e293b")
    categories = ["Net Agent", "LLM Inference", "Tool Exec", "Overall P50"]
    lat_vals = [
        lat.get("agent_thinking_p50", 1200.0),
        lat.get("llm_generation_p50", 1700.0),
        lat.get("tool_execution_p50", 3300.0),
        lat.get("overall_p50", 2000.0)
    ]
    colors = ["#38bdf8", "#818cf8", "#f43f5e", "#34d399"]
    bars = ax_lat.bar(categories, lat_vals, color=colors, width=0.55)
    ax_lat.set_title("Latency Breakdown (P50 ms)", fontsize=11, fontweight="bold", color="#f8fafc", pad=10)
    ax_lat.tick_params(colors="#94a3b8", labelsize=8)
    ax_lat.grid(axis="y", color="#334155", linestyle="--", alpha=0.7)
    for bar in bars:
        h = bar.get_height()
        ax_lat.text(bar.get_x() + bar.get_width() / 2, h + 50, f"{int(h)}ms", ha="center", va="bottom", color="#e2e8f0", fontsize=8)

    # 4. DeepEval Benchmark (Top Right)
    ax_eval = fig.add_subplot(gs[0, 2])
    ax_eval.set_facecolor("#1e293b")
    eval_names = ["Grounded Acc", "Halluc Recall", "Pass Rate"]
    eval_scores = [
        kpi.get("grounded_accuracy_score", 1.0) * 100,
        kpi.get("hallucination_detection_recall", 1.0) * 100,
        kpi.get("measured_success_rate", 1.0) * 100
    ]
    eval_bars = ax_eval.barh(eval_names, eval_scores, color=["#10b981", "#6366f1", "#0ea5e9"], height=0.45)
    ax_eval.set_xlim(0, 115)
    ax_eval.set_title("DeepEval LLM-Judge Benchmark", fontsize=11, fontweight="bold", color="#f8fafc", pad=10)
    ax_eval.tick_params(colors="#94a3b8", labelsize=8)
    ax_eval.grid(axis="x", color="#334155", linestyle="--", alpha=0.7)
    for bar in eval_bars:
        w = bar.get_width()
        ax_eval.text(w + 2, bar.get_y() + bar.get_height() / 2, f"{w:.1f}%", ha="left", va="center", color="#e2e8f0", fontsize=8)

    # 5. Pipeline Architecture Diagram (Bottom Span)
    ax_arch = fig.add_subplot(gs[1, :])
    ax_arch.set_facecolor("#1e293b")
    ax_arch.axis("off")
    ax_arch.text(0.04, 0.88, "LANGGRAPH MULTI-AGENT WORKFLOW & SECURITY TOPOLOGY", fontsize=11, fontweight="bold", color="#f8fafc")
    
    stages = [
        ("1. Input Guardrails\nPII Mask & Threat Quarantine", 0.04, "#ef4444"),
        ("2. Supervisor Node\nRouting & Threat Gate", 0.23, "#f59e0b"),
        ("3. Classification Agent\nSeverity & Loss Estimator", 0.42, "#3b82f6"),
        ("4. Coverage Agent\nStdio MCP & FAISS RAG", 0.61, "#8b5cf6"),
        ("5. Fraud & Tiered Memory\nLangMem Semantic Store", 0.80, "#10b981")
    ]
    for text, x, col in stages:
        rect = plt.Rectangle((x, 0.25), 0.16, 0.48, facecolor="#0f172a", edgecolor=col, linewidth=2, transform=ax_arch.transAxes)
        ax_arch.add_patch(rect)
        ax_arch.text(x + 0.08, 0.49, text, color="#f8fafc", fontsize=8, ha="center", va="center", transform=ax_arch.transAxes, fontweight="medium")

    os.makedirs(os.path.dirname(output_png_path), exist_ok=True)
    plt.savefig(output_png_path, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    print(f"[DashboardGen] Generated operational dashboard image at {output_png_path}")


if __name__ == "__main__":
    generate_dashboard_image()
