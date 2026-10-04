import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches

os.makedirs(r"c:\Users\lakha\ml_cp\SMBFlow\research paper\figures", exist_ok=True)

plt.rcParams["font.sans-serif"] = "DejaVu Sans"
plt.rcParams["font.family"] = "sans-serif"

def generate_fig_architecture():
    fig, ax = plt.subplots(figsize=(11, 6.5), dpi=300)
    ax.axis("off")
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 6.5)

    layers = [
        ("Presentation & Operations Layer (React 18, Vite, WebSockets, Monaco, React Flow)", 0.5, 5.2, 10.0, 0.8, "#E3F2FD", "#1565C0"),
        ("API & Gateway Layer (FastAPI, JWT Auth, Multi-Tenant RBAC, MultiFernet Vault)", 0.5, 4.0, 10.0, 0.8, "#E8F5E9", "#2E7D32"),
        ("Workflow Orchestration Layer (Custom DAG Engine, StateManager, Signal Collector)", 0.5, 2.8, 10.0, 0.8, "#FFF3E0", "#E65100"),
        ("Multi-Agent & Intelligence Engine (6-Agent Pipeline, LiteLLM, RAG + GraphRAG)", 0.5, 1.6, 10.0, 0.8, "#F3E5F5", "#6A1B9A"),
        ("Persistence & Audit Infrastructure (PostgreSQL 16 + pgvector, Redis, EPI Provenance)", 0.5, 0.4, 10.0, 0.8, "#ECEFF1", "#37474F"),
    ]

    for title, x, y, w, h, bg, border in layers:
        rect = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04", facecolor=bg, edgecolor=border, linewidth=1.5)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h/2, title, ha="center", va="center", fontsize=9.5, fontweight="bold", color=border)

    for y in [5.1, 3.9, 2.7, 1.5]:
        ax.annotate("", xy=(5.5, y), xytext=(5.5, y + 0.1),
                    arrowprops=dict(arrowstyle="->", lw=1.8, color="#37474F", mutation_scale=15))

    plt.tight_layout()
    plt.savefig(r"c:\Users\lakha\ml_cp\SMBFlow\research paper\figures\fig_architecture.png", bbox_inches="tight")
    plt.close()
    print("Saved fig_architecture.png")

def generate_fig_agent_pipeline():
    fig, ax = plt.subplots(figsize=(12, 3.5), dpi=300)
    ax.axis("off")
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 3.5)

    agents = [
        ("1. Research\nAgent", "Signal Intake\n& RAG Retrieval", 0.4, "#E1F5FE", "#0288D1"),
        ("2. Reasoning\nAgent", "Risk Analysis\n& Strategy", 2.3, "#FFF3E0", "#F57C00"),
        ("3. Drafting\nAgent", "Tool Proposals\n& Content Drafts", 4.2, "#E8F5E9", "#388E3C"),
        ("4. Verification\nAgent", "Policy Audit\n& Rules Check", 6.1, "#FFEBEE", "#D32F2F"),
        ("5. Execution\nAgent", "Tool Execution\n& Webhooks", 8.0, "#EDE7F6", "#512DA8"),
        ("6. Memory\nAgent", "GraphRAG & DB\nState Update", 9.9, "#E0F2F1", "#00796B"),
    ]

    for name, desc, x, bg, border in agents:
        rect = patches.FancyBboxPatch((x, 0.8), 1.6, 1.8, boxstyle="round,pad=0.04", facecolor=bg, edgecolor=border, linewidth=1.5)
        ax.add_patch(rect)
        ax.text(x + 0.8, 2.1, name, ha="center", va="center", fontsize=9, fontweight="bold", color=border)
        ax.text(x + 0.8, 1.3, desc, ha="center", va="center", fontsize=7.5, color="#37474F")

    for i in range(len(agents) - 1):
        x_start = agents[i][2] + 1.6
        x_end = agents[i+1][2]
        ax.annotate("", xy=(x_end, 1.7), xytext=(x_start, 1.7),
                    arrowprops=dict(arrowstyle="->", lw=1.6, color="#424242", mutation_scale=12))

    plt.tight_layout()
    plt.savefig(r"c:\Users\lakha\ml_cp\SMBFlow\research paper\figures\fig_agent_pipeline.png", bbox_inches="tight")
    plt.close()
    print("Saved fig_agent_pipeline.png")

def generate_fig_governance_hitl():
    fig, ax = plt.subplots(figsize=(10.5, 5.5), dpi=300)
    ax.axis("off")
    ax.set_xlim(0, 10.5)
    ax.set_ylim(0, 5.5)

    boxes = [
        ("Agent Action Proposal\n(Drafting Agent)", 0.5, 3.4, 2.3, 1.3, "#E3F2FD", "#1565C0"),
        ("Deterministic Policy Gate\n(Verification Agent)", 3.8, 3.4, 2.5, 1.3, "#FFF3E0", "#E65100"),
        ("HITL Approval Queue\n(Human Operator)", 7.3, 3.4, 2.5, 1.3, "#FFEBEE", "#C62828"),
        ("Tool Execution\n(HubSpot / Gmail / Slack)", 7.3, 0.7, 2.5, 1.3, "#E8F5E9", "#2E7D32"),
        ("EPI Audit Provenance\n(Tamper-Evident .epi Log)", 3.8, 0.7, 2.5, 1.3, "#ECEFF1", "#37474F"),
    ]

    for title, x, y, w, h, bg, border in boxes:
        rect = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04", facecolor=bg, edgecolor=border, linewidth=1.5)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h/2, title, ha="center", va="center", fontsize=8.5, fontweight="bold", color=border)

    # Arrow 1: Proposal -> Policy Gate
    ax.annotate("", xy=(3.8, 4.05), xytext=(2.8, 4.05), arrowprops=dict(arrowstyle="->", lw=1.6, color="#37474F", mutation_scale=12))
    
    # Arrow 2: Policy Gate -> HITL Queue
    ax.annotate("", xy=(7.3, 4.05), xytext=(6.3, 4.05), arrowprops=dict(arrowstyle="->", lw=1.6, color="#C62828", mutation_scale=12))
    ax.text(6.8, 4.3, "Requires HITL", ha="center", va="center", fontsize=8, fontweight="bold", color="#C62828")

    # Arrow 3: HITL Queue -> Tool Execution
    ax.annotate("", xy=(8.55, 2.0), xytext=(8.55, 3.4), arrowprops=dict(arrowstyle="->", lw=1.6, color="#2E7D32", mutation_scale=12))
    ax.text(8.9, 2.7, "Approved", ha="left", va="center", fontsize=8.5, fontweight="bold", color="#2E7D32")

    # Arrow 4: Tool Execution -> EPI Audit Log
    ax.annotate("", xy=(6.3, 1.35), xytext=(7.3, 1.35), arrowprops=dict(arrowstyle="->", lw=1.6, color="#37474F", mutation_scale=12))
    ax.text(6.8, 1.6, "Record Log", ha="center", va="center", fontsize=8, color="#37474F")

    # Arrow 5: Policy Gate Low-Risk Direct Execution (Dashed line down then right)
    ax.annotate("", xy=(5.05, 2.0), xytext=(5.05, 3.4), arrowprops=dict(arrowstyle="->", lw=1.6, color="#2E7D32", linestyle="dashed", mutation_scale=12))
    ax.text(4.9, 2.7, "Low Risk\n(Auto Pass)", ha="right", va="center", fontsize=8, color="#2E7D32")
    ax.annotate("", xy=(7.3, 1.35), xytext=(5.05, 1.35), arrowprops=dict(arrowstyle="->", lw=1.6, color="#2E7D32", linestyle="dashed", mutation_scale=12))

    plt.tight_layout()
    plt.savefig(r"c:\Users\lakha\ml_cp\SMBFlow\research paper\figures\fig_governance_hitl.png", bbox_inches="tight")
    plt.close()
    print("Saved fig_governance_hitl.png")

def generate_fig_closed_loop_feedback():
    fig, ax = plt.subplots(figsize=(9.5, 5.5), dpi=300)
    ax.axis("off")
    ax.set_xlim(0, 9.5)
    ax.set_ylim(0, 5.5)

    boxes = [
        ("1. Tool Action Execution\n(HubSpot / Gmail / Slack)", 0.6, 3.2, 3.6, 1.4, "#E8F5E9", "#2E7D32"),
        ("2. Outcome Measurement\n(core/outcome_tracker.py)", 5.3, 3.2, 3.6, 1.4, "#FFF3E0", "#E65100"),
        ("3. GraphRAG Entity Update\n(NetworkX Knowledge Graph)", 5.3, 0.6, 3.6, 1.4, "#F3E5F5", "#6A1B9A"),
        ("4. Context Enrichment\n(Historical Pattern Memory)", 0.6, 0.6, 3.6, 1.4, "#E3F2FD", "#1565C0"),
    ]

    for title, x, y, w, h, bg, border in boxes:
        rect = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05", facecolor=bg, edgecolor=border, linewidth=1.6)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h/2, title, ha="center", va="center", fontsize=9, fontweight="bold", color=border)

    ax.annotate("", xy=(5.3, 3.9), xytext=(4.2, 3.9),
                arrowprops=dict(arrowstyle="->", lw=1.8, color="#37474F", mutation_scale=14))
    ax.text(4.75, 4.15, "Status & Metrics", ha="center", va="center", fontsize=8, color="#37474F")

    ax.annotate("", xy=(7.1, 2.0), xytext=(7.1, 3.2),
                arrowprops=dict(arrowstyle="->", lw=1.8, color="#37474F", mutation_scale=14))
    ax.text(7.25, 2.6, "Store Graph Edge", ha="left", va="center", fontsize=8, color="#37474F")

    ax.annotate("", xy=(4.2, 1.3), xytext=(5.3, 1.3),
                arrowprops=dict(arrowstyle="->", lw=1.8, color="#6A1B9A", mutation_scale=14))
    ax.text(4.75, 1.05, "Retrieve Similar Patterns", ha="center", va="center", fontsize=8, fontweight="bold", color="#6A1B9A")

    ax.annotate("", xy=(2.4, 3.2), xytext=(2.4, 2.0),
                arrowprops=dict(arrowstyle="->", lw=1.8, color="#1565C0", mutation_scale=14))
    ax.text(2.25, 2.6, "Enrich Next Action Context", ha="right", va="center", fontsize=8, fontweight="bold", color="#1565C0")

    plt.tight_layout()
    plt.savefig(r"c:\Users\lakha\ml_cp\SMBFlow\research paper\figures\fig_closed_loop_feedback.png", bbox_inches="tight")
    plt.close()
    print("Saved fig_closed_loop_feedback.png")

if __name__ == "__main__":
    generate_fig_architecture()
    generate_fig_agent_pipeline()
    generate_fig_governance_hitl()
    generate_fig_closed_loop_feedback()
