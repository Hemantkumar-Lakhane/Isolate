# 📄 SMBFlow IEEE Research Paper Workspace

This directory contains the full IEEE format LaTeX research paper, vector/raster architecture diagrams, BibTeX references, and section modules for **SMBFlow**.

---

## 🎯 Research Paper Objective
To present a formal academic research paper introducing **SMBFlow**, an enterprise-grade multi-agent workflow automation framework that combines probabilistic AI reasoning with deterministic policy governance, Human-in-the-Loop (HITL) approval, and cryptographic audit provenance for Small and Medium Enterprises (SMEs).

---

## 🔬 Core Research Question
> *"How can probabilistic AI intelligence (LLMs & autonomous multi-agent pipelines) be bounded within a deterministic workflow orchestration and policy governance framework to execute context-aware, verifiable, and policy-compliant business actions for Small and Medium Enterprises?"*

---

## 📁 Workspace Structure

```
SMBFlow/research paper/
├── main.tex                       # Master IEEE LaTeX document
├── references.bib                 # Clean IEEE BibTeX bibliography entries
├── README.md                      # Paper overview & compilation documentation
├── figures/                       # Vector/raster architecture diagrams
│   ├── fig_architecture.png       # Overall SMBFlow System Architecture
│   ├── fig_agent_pipeline.png     # 6-Stage Multi-Agent Pipeline
│   ├── fig_governance_hitl.png    # Policy Verification & HITL Flow
│   └── fig_closed_loop_feedback.png # Closed-Loop GraphRAG Outcome Feedback
└── sections/                      # Modular LaTeX section files
    ├── 01_introduction.tex
    ├── 02_related_work.tex
    ├── 03_problem_formulation.tex
    ├── 04_proposed_framework.tex
    ├── 05_methodology.tex
    ├── 06_implementation.tex
    ├── 07_evaluation_framework.tex
    ├── 08_results_discussion.tex
    ├── 09_limitations.tex
    ├── 10_future_work.tex
    └── 11_conclusion.tex
```

---

## 🛠️ Implemented Codebase Components Used as Evidence

* **DAG Workflow Orchestrator**: [`core/orchestrator.py`](file:///c:/Users/lakha/ml_cp/SMBFlow/core/orchestrator.py) & [`core/state_manager.py`](file:///c:/Users/lakha/ml_cp/SMBFlow/core/state_manager.py)
* **Six-Stage Multi-Agent Engine**: [`agents/agents.py`](file:///c:/Users/lakha/ml_cp/SMBFlow/agents/agents.py) & [`agents/base_agent.py`](file:///c:/Users/lakha/ml_cp/SMBFlow/agents/base_agent.py)
* **Multi-LLM Router**: [`core/llm_router.py`](file:///c:/Users/lakha/ml_cp/SMBFlow/core/llm_router.py) (LiteLLM with Anthropic, Groq, OpenAI, Gemini)
* **Hybrid Context Retrieval**: [`core/rag_engine.py`](file:///c:/Users/lakha/ml_cp/SMBFlow/core/rag_engine.py) (`pgvector`) & [`core/graph_rag.py`](file:///c:/Users/lakha/ml_cp/SMBFlow/core/graph_rag.py) (`NetworkX` GraphRAG)
* **Audit Provenance Infrastructure**: [`epi/epi_manager.py`](file:///c:/Users/lakha/ml_cp/SMBFlow/epi/epi_manager.py) (`.epi` cryptographic logs)
* **Human-in-the-Loop Approval Queue**: [`api/routers/connections.py`](file:///c:/Users/lakha/ml_cp/SMBFlow/api/routers/connections.py) & React Action Center UI
* **Concrete Case-Study Instance**: Product Launch Workflow ([`api/routers/product_launch.py`](file:///c:/Users/lakha/ml_cp/SMBFlow/api/routers/product_launch.py), [`tests/test_product_launch.py`](file:///c:/Users/lakha/ml_cp/SMBFlow/tests/test_product_launch.py))

---

## 📊 Status of Experiments & Evaluation

1. **Completed Empirical Measurements**:
   * Agent execution stage latency breakdown (Table I in Section VIII).
   * Token cost tracking per execution pass (`core/cost_tracker.py`).
   * Verification agent policy blocking rate (100% policy enforcement).
   * EPI audit trail SHA-256 hash validation.
2. **Pending / Future Benchmarks**:
   * Multi-tenant stress testing under 1,000 concurrent DAG executions (marked as `[EXTENDED MULTI-TENANT BENCHMARK RESULTS TO BE POPULATED UPON FULL DATASET EVALUATION PASS]`).

---

## 🖼️ Figures Generated

1. `figures/fig_architecture.png` — High-resolution system architecture diagram detailing UI, Gateway, DAG Orchestrator, Multi-Agent Engine, and Persistence layers.
2. `figures/fig_agent_pipeline.png` — Diagram of the 6-stage sequential agent pipeline (Research $\rightarrow$ Reasoning $\rightarrow$ Drafting $\rightarrow$ Verification $\rightarrow$ Execution $\rightarrow$ Memory).
3. `figures/fig_governance_hitl.png` — Workflow of the deterministic policy gate and Human-in-the-Loop approval queue.
4. `figures/fig_closed_loop_feedback.png` — Closed-loop outcome tracker updating the GraphRAG knowledge graph memory.

---

## 📚 References & Bibliography Source
All citations in `references.bib` are grounded in published academic computer science literature (IEEE, ACM, NeurIPS, Springer, W3C) covering multi-agent systems, workflow orchestration, RAG, GraphRAG, human-AI interaction, process mining, and data provenance.

---

## ⚙️ How to Compile the Paper

To compile the LaTeX paper to PDF:
```bash
# Using latexmk (recommended)
latexmk -pdf main.tex

# OR using pdflatex + bibtex manually
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```
