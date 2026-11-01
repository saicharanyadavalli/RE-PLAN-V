# Benchmark Methodology & Empirical Complexity Tiers

## 1. Zero-Fabrication Metric Integrity

RE-PLAN-V adheres strictly to empirical measurement standards:
- **No hardcoded accuracy values**: Metrics are derived solely from live test and evaluation runs.
- **Controlled Seeds**: Benchmark instances are generated using deterministic random seeds to guarantee scientific reproducibility.
- **No Silent Dropping**: Unsolved, timed-out, or failed problems are counted honestly as failures.

---

## 2. Empirical Complexity Tiers (100–3000 States)

The benchmark generator (`benchmark/generator/multi_domain_generator.py`) generates problems spanning 5 complexity tiers:

| Tier | Unique State Range | Typical Domains | Characteristics |
| :--- | :--- | :--- | :--- |
| **Tiny** | $< 50$ states | Software Workflow, 2-Block Stacking | Rapid convergence, short horizon ($< 4$ steps). |
| **Small** | $50 - 200$ states | Blocks World (3 blocks), Job Scheduling | Shallow branching, high reachability density. |
| **Medium** | $200 - 1000$ states | Grid World ($5\times 5$), Household Robotics | Multi-room navigation, intermediate combinatorial branching. |
| **Large** | $1000 - 3000$ states | Warehouse Logistics (Multiple SKUs / AGVs) | Extensive reachable state spaces, deep paths. |
| **Stress** | $> 3000$ states | Multi-robot grid transfer with obstacles | Frontier budget limits tested (`MAX_NODES_EXCEEDED`). |

---

## 3. Reproduction Command

To reproduce the multi-stage research evaluation results locally:
```bash
python scripts/reproduce_results.py
```
This script executes:
1. Stage 1: Classical 10-problem planning suite.
2. Stage 2: 5-class fault attribution confusion matrix.
3. Stage 3: Dynamic world perturbation & replanning.
4. Stage 4: Multi-Domain Complexity Tier evaluation across all 6 domains.
