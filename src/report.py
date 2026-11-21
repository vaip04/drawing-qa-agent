"""HTML and visual plan report generator for Drawing QA Agent."""

from pathlib import Path
import jinja2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from shapely.geometry import Polygon

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Drawing Review Report - {{ pkg.brief.project }}</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 2rem; background: #fdfdfd; color: #222; }
  h1, h2, h3 { color: #111; }
  .badge { display: inline-block; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.85rem; font-weight: bold; }
  .badge-failed { background: #ffebe9; color: #cf222e; border: 1px solid #ff8182; }
  .badge-review { background: #fff8c5; color: #9a6700; border: 1px solid #d4a72c; }
  .badge-high { background: #cf222e; color: #fff; }
  .badge-medium { background: #fb8f44; color: #fff; }
  .badge-low { background: #54aeff; color: #fff; }
  .summary-card { background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 6px; padding: 1.25rem; margin-bottom: 2rem; display: flex; gap: 2rem; }
  .metric { display: flex; flex-direction: column; }
  .metric-val { font-size: 1.8rem; font-weight: bold; }
  .metric-lbl { color: #57609a; font-size: 0.85rem; text-transform: uppercase; }
  table { width: 100%; border-collapse: collapse; margin-top: 1rem; margin-bottom: 2rem; font-size: 0.9rem; }
  th, td { border: 1px solid #d0d7de; padding: 8px 12px; text-align: left; }
  th { background-color: #f6f8fa; }
  tr:nth-child(even) { background-color: #fafbfc; }
  .plan-container { margin: 2rem 0; }
  .plan-img { max-width: 100%; height: auto; border: 1px solid #d0d7de; border-radius: 6px; }
  .guardrail-log { background: #f6f8fa; border-left: 4px solid #0969da; padding: 1rem; border-radius: 4px; margin-top: 1rem; }
  .prose-summary { background: #e8f4fc; border-left: 4px solid #1f883d; padding: 1rem; border-radius: 4px; margin-bottom: 1.5rem; font-style: italic; }
</style>
</head>
<body>
  <h1>Drawing QA Review Report</h1>
  <div class="summary-card">
    <div class="metric"><span class="metric-val">{{ pkg.brief.project }}</span><span class="metric-lbl">Project</span></div>
    <div class="metric"><span class="metric-val">{{ pkg.brief.brief_version }}</span><span class="metric-lbl">Brief Version</span></div>
    <div class="metric"><span class="metric-val">{{ mode }}</span><span class="metric-lbl">Execution Mode</span></div>
    <div class="metric"><span class="metric-val" style="color: #cf222e;">{{ counts.rule_failed }}</span><span class="metric-lbl">Rule Failed</span></div>
    <div class="metric"><span class="metric-val" style="color: #9a6700;">{{ counts.needs_review }}</span><span class="metric-lbl">Needs Review</span></div>
  </div>

  {% if llm_summary %}
  <h2>Architect Review Summary</h2>
  <div class="prose-summary">
    {{ llm_summary | replace('\\n', '<br>') }}
  </div>
  {% endif %}

  <h2>1. Rule Failed (Objective / Code-measured)</h2>
  {% if failed_findings %}
  <table>
    <thead>
      <tr>
        <th>Rule</th>
        <th>Severity</th>
        <th>Sheet</th>
        <th>Element</th>
        <th>Issue Description</th>
        <th>Evidence</th>
        {% if mode == "LLM" %}<th>Agent Reviewer Note</th>{% endif %}
      </tr>
    </thead>
    <tbody>
      {% for f in failed_findings %}
      <tr>
        <td><code>{{ f.rule_id }}</code></td>
        <td><span class="badge badge-{{ f.severity }}">{{ f.severity | upper }}</span></td>
        <td>{{ f.sheet_no or "-" }}</td>
        <td><strong>{{ f.element }}</strong></td>
        <td>{{ f.issue }}</td>
        <td><code>{{ f.evidence }}</code></td>
        {% if mode == "LLM" %}<td>{{ f.llm_note or "-" }}</td>{% endif %}
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
  <p><em>No rule failures detected. All deterministic checks passed.</em></p>
  {% endif %}

  <h2>2. Needs Human Review (Judgement & Intent)</h2>
  {% if review_findings %}
  <table>
    <thead>
      <tr>
        <th>Rule</th>
        <th>Severity</th>
        <th>Sheet</th>
        <th>Element</th>
        <th>Observation</th>
        <th>Evidence</th>
        {% if mode == "LLM" %}<th>Agent Reviewer Note</th>{% endif %}
      </tr>
    </thead>
    <tbody>
      {% for f in review_findings %}
      <tr>
        <td><code>{{ f.rule_id }}</code></td>
        <td><span class="badge badge-{{ f.severity }}">{{ f.severity | upper }}</span></td>
        <td>{{ f.sheet_no or "-" }}</td>
        <td><strong>{{ f.element }}</strong></td>
        <td>{{ f.issue }}</td>
        <td><code>{{ f.evidence }}</code></td>
        {% if mode == "LLM" %}<td>{{ f.llm_note or "-" }}</td>{% endif %}
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
  <p><em>No items flagged for human review.</em></p>
  {% endif %}

  <h2>3. Annotated Drawing Plan</h2>
  <div class="plan-container">
    <img src="plan_annotated.png" alt="Annotated Plan" class="plan-img">
  </div>

  <h2>4. Guardrail Verification Log</h2>
  <div class="guardrail-log">
    <p><strong>Guardrail Status:</strong> Active</p>
    <p><strong>Rejected / Hallucinated Findings Dropped:</strong> {{ guardrail_log.rejected_unsupported | length }}</p>
    <p><strong>Restored Tampered Findings:</strong> {{ guardrail_log.restored_count }}</p>
    {% if guardrail_log.rejected_unsupported %}
    <ul>
      {% for r in guardrail_log.rejected_unsupported %}
      <li><code>{{ r }}</code></li>
      {% endfor %}
    </ul>
    {% endif %}
  </div>

  <p style="margin-top: 3rem; color: #888; font-size: 0.8rem;">
    Generated by Drawing QA Agent &bull; <em>AI proposes, code checks, people approve.</em>
  </p>
</body>
</html>
"""


def generate_annotated_plan(pkg: dict, findings: list, out_path: Path):
    """Render annotated floor plans with failing rooms highlighted in red and labelled with rule IDs."""
    rooms = pkg.get("rooms")
    if rooms is None or rooms.empty:
        return

    # Identify failing elements and map to room names
    failing_rooms = {}
    for f in findings:
        elem = f.get("element", "")
        rid = f.get("rule_id", "")
        # Add to room mapping
        if elem not in failing_rooms:
            failing_rooms[elem] = []
        failing_rooms[elem].append(rid)

    floors = sorted(rooms["floor"].unique())
    num_floors = len(floors)

    fig, axes = plt.subplots(1, max(num_floors, 1), figsize=(7 * num_floors, 7), squeeze=False)
    axes = axes[0]

    for idx, floor in enumerate(floors):
        ax = axes[idx]
        floor_rooms = rooms[rooms["floor"] == floor]

        for _, r in floor_rooms.iterrows():
            verts = r["polygon"]
            if not verts or len(verts) < 3:
                continue

            rname = r["name"]
            is_failed = False
            flag_rules = []

            # Check direct or partial match
            for felem, rids in failing_rooms.items():
                if felem.lower() in rname.lower() or rname.lower() in felem.lower():
                    is_failed = True
                    flag_rules.extend(rids)

            edgecolor = "#d73a49" if is_failed else "#24292f"
            facecolor = "#ffdce0" if is_failed else "#f1f8ff"
            linewidth = 2.5 if is_failed else 1.2

            poly_patch = plt.Polygon(
                verts, closed=True, fill=True,
                facecolor=facecolor, edgecolor=edgecolor,
                linewidth=linewidth
            )
            ax.add_patch(poly_patch)

            # Center text
            cx = sum(v[0] for v in verts) / len(verts)
            cy = sum(v[1] for v in verts) / len(verts)

            label = rname
            if is_failed and flag_rules:
                unique_rules = sorted(set(flag_rules))
                label += f"\n[{','.join(unique_rules)}]"

            ax.text(
                cx, cy, label,
                ha="center", va="center",
                fontsize=8, weight="bold" if is_failed else "normal",
                color="#b31d28" if is_failed else "#0969da"
            )

        ax.set_aspect("equal", "datalim")
        ax.autoscale()
        ax.set_title(f"Floor {floor} Plan", fontsize=11, weight="bold")
        ax.set_xlabel("Feet (x)")
        ax.set_ylabel("Feet (y)")
        ax.grid(True, linestyle="--", alpha=0.4)

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def render_html_report(pkg: dict, findings: list, out_path: Path, mode: str = "NO-LLM",
                       llm_summary: str = "", guardrail_log: dict = None):
    """Render full HTML review report."""
    if guardrail_log is None:
        guardrail_log = {"rejected_unsupported": [], "restored_count": 0}

    # Sort severity order: high > medium > low
    sev_order = {"high": 0, "medium": 1, "low": 2}
    sorted_findings = sorted(findings, key=lambda f: sev_order.get(f.get("severity", "low"), 3))

    failed = [f for f in sorted_findings if f.get("group") == "RULE_FAILED"]
    review = [f for f in sorted_findings if f.get("group") == "NEEDS_REVIEW"]

    counts = {
        "rule_failed": len(failed),
        "needs_review": len(review),
    }

    template = jinja2.Template(HTML_TEMPLATE)
    rendered = template.render(
        pkg=pkg,
        findings=sorted_findings,
        failed_findings=failed,
        review_findings=review,
        counts=counts,
        mode=mode,
        llm_summary=llm_summary,
        guardrail_log=guardrail_log,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(rendered)
