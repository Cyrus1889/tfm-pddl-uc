

"""
verificar_y_visualizar_plan_priorizado.py

Uso:
  python scripts/verificar_y_visualizar_plan_priorizado.py <ruta_problem_pddl> <ruta_plan_txt>


"""

from __future__ import annotations

import re
import sys
import os
from pathlib import Path
from collections import defaultdict, OrderedDict
from typing import Dict, Tuple, List, Optional

# --- Dependencias opcionales (errores amigables si faltan) ---
try:
    import pandas as pd
except Exception:
    pd = None

try:
    import matplotlib.pyplot as plt
except Exception:
    plt = None


# =========================
# Expresiones regulares
# =========================

RGX_ACTION = re.compile(
    r'\(\s*(?P<action>despachar_(?:pv|hidro|termica)|marcar_(?:pv|hidro)_agotado|avanzar_hora)\s+'
    r'(?P<h1>h\d{1,2})(?:\s+(?P<h2>h\d{1,2}))?\s*\)',
    re.IGNORECASE
)

RGX_ESCALAR = {
    "costo_pv": re.compile(r"\(=\s*\(costo_pv\)\s*([+-]?\d+(?:\.\d+)?)\)", re.IGNORECASE),
    "costo_hidro": re.compile(r"\(=\s*\(costo_hidro\)\s*([+-]?\d+(?:\.\d+)?)\)", re.IGNORECASE),
    "costo_termica": re.compile(r"\(=\s*\(costo_termica\)\s*([+-]?\d+(?:\.\d+)?)\)", re.IGNORECASE),
    "unidad_despacho": re.compile(r"\(=\s*\(unidad_despacho\)\s*([+-]?\d+(?:\.\d+)?)\)", re.IGNORECASE),
}

RGX_SERIES = {
    "demanda": re.compile(r"\(=\s*\(demanda\s+(h\d{1,2})\)\s*([+-]?\d+(?:\.\d+)?)\)", re.IGNORECASE),
    "pv": re.compile(r"\(=\s*\(pv_disponible\s+(h\d{1,2})\)\s*([+-]?\d+(?:\.\d+)?)\)", re.IGNORECASE),
    "hidro": re.compile(r"\(=\s*\(hidro_disponible_hora\s+(h\d{1,2})\)\s*([+-]?\d+(?:\.\d+)?)\)", re.IGNORECASE),
    "termica": re.compile(r"\(=\s*\(termica_disponible_hora\s+(h\d{1,2})\)\s*([+-]?\d+(?:\.\d+)?)\)", re.IGNORECASE),
}


# =========================
# Utilidades
# =========================

def hour_key(h: str) -> int:
    try:
        return int(h[1:])
    except Exception:
        return 10**9

def ensure_results_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


# =========================
# Parseadores
# =========================

def parse_plan(plan_path: Path):
    text = plan_path.read_text(encoding="utf-8", errors="ignore")
    markers: List[Tuple[str, str, Optional[str]]] = []

    for m in RGX_ACTION.finditer(text):
        action = m.group("action").lower()
        h1 = (m.group("h1") or "").lower()
        h2 = (m.group("h2") or None)
        if h2:
            h2 = h2.lower()
        markers.append((action, h1, h2))

    return markers


def parse_problem(problem_path: Path):
    text = problem_path.read_text(encoding="utf-8", errors="ignore")

    esc: Dict[str, float] = {}
    for key, rgx in RGX_ESCALAR.items():
        m = rgx.search(text)
        if not m:
            raise ValueError(f"No se encontró el parámetro '{key}' en {problem_path.name}")
        esc[key] = float(m.group(1))

    series: Dict[str, Dict[str, float]] = {k: {} for k in RGX_SERIES.keys()}
    for k, rgx in RGX_SERIES.items():
        for m in rgx.finditer(text):
            h = m.group(1).lower()
            val = float(m.group(2))
            series[k][h] = val

    return {
        "unidad_despacho": esc["unidad_despacho"],
        "costo_pv": esc["costo_pv"],
        "costo_hidro": esc["costo_hidro"],
        "costo_termica": esc["costo_termica"],
        "demanda": series["demanda"],
        "cap_pv": series["pv"],
        "cap_hidro": series["hidro"],
        "cap_termica": series["termica"],
    }


# =========================
# Simulación del plan (clave para reflejar h23)
# =========================

def simulate_plan(markers: List[Tuple[str, str, Optional[str]]], params: Dict):
    """
    Devuelve:
      - counts[h]['pv'|'hidro'|'termica'] = cantidad de acciones
      - demanda_final[h] = demanda inicial - despachos realizados en h
      - ultimo_to = última hora alcanzada via (avanzar_hora hX hY)  -> hY
    """
    unidad = params["unidad_despacho"]
    demanda_ini: Dict[str, float] = dict(params.get("demanda", {}))

    # Estructuras de simulación
    counts = defaultdict(lambda: defaultdict(int))
    demanda_final = dict(demanda_ini)  # copia
    ultimo_to: Optional[str] = None

    for (act, h1, h2) in markers:
        if act.startswith("despachar_"):
            src = act.split("_", 1)[1]  # pv | hidro | termica
            counts[h1][src] += 1
            # Aplica el efecto sobre la demanda de esa hora
            if h1 not in demanda_final:
                # si no estaba, arranca desde 0 (seguro no pasa en tu problem, pero por robustez)
                demanda_final[h1] = 0.0
            demanda_final[h1] = demanda_final[h1] - unidad
        elif act == "avanzar_hora" and h2:
            ultimo_to = h2

    return counts, demanda_final, ultimo_to


# =========================
# Construcción de resumen
# =========================

def build_summary(counts, demanda_final, params):
    unidad = params["unidad_despacho"]
    c_pv = params["costo_pv"]
    c_h = params["costo_hidro"]
    c_t = params["costo_termica"]

    demanda_ini = params.get("demanda", {})
    horas = set(demanda_ini.keys()) | set(counts.keys()) | set(demanda_final.keys())
    horas = sorted(horas, key=hour_key)

    rows = []
    tot = {
        "pv_mw": 0.0, "hidro_mw": 0.0, "termica_mw": 0.0,
        "costo_pv": 0.0, "costo_hidro": 0.0, "costo_termica": 0.0,
    }
    costo_acum = 0.0

    for h in horas:
        n_pv = counts[h].get("pv", 0)
        n_h = counts[h].get("hidro", 0)
        n_t = counts[h].get("termica", 0)

        pv_mw = n_pv * unidad
        h_mw = n_h * unidad
        t_mw = n_t * unidad

        costo_pv = pv_mw * c_pv
        costo_h = h_mw * c_h
        costo_t = t_mw * c_t

        costo_hora = costo_pv + costo_h + costo_t
        costo_acum += costo_hora

        dem_ini = demanda_ini.get(h, None)
        dem_res = demanda_final.get(h, None)
        total_mw = pv_mw + h_mw + t_mw

        rows.append(OrderedDict([
            ("hora", h),
            ("demanda_inicial", dem_ini if dem_ini is not None else ""),
            ("pv_mw", pv_mw),
            ("hidro_mw", h_mw),
            ("termica_mw", t_mw),
            ("total_despachado_mw", total_mw),
            ("demanda_residual", dem_res if dem_res is not None else ""),
            ("costo_pv", costo_pv),
            ("costo_hidro", costo_h),
            ("costo_termica", costo_t),
            ("costo_acumulado", costo_acum),
        ]))

        tot["pv_mw"] += pv_mw
        tot["hidro_mw"] += h_mw
        tot["termica_mw"] += t_mw
        tot["costo_pv"] += costo_pv
        tot["costo_hidro"] += costo_h
        tot["costo_termica"] += costo_t

    return rows, tot


# =========================
# Verificación
# =========================

def verify(rows: List[Dict], params: Dict) -> List[str]:
    caps_pv = params.get("cap_pv", {})
    caps_h = params.get("cap_hidro", {})
    caps_t = params.get("cap_termica", {})
    warnings: List[str] = []

    for r in rows:
        h = r["hora"]
        pv_mw = r["pv_mw"]
        h_mw = r["hidro_mw"]
        t_mw = r["termica_mw"]

        cap_pv = caps_pv.get(h, None)
        cap_h = caps_h.get(h, None)
        cap_t = caps_t.get(h, None)

        if cap_pv is not None and pv_mw > cap_pv + 1e-6:
            warnings.append(f"[{h}] PV excede capacidad: usado={pv_mw} > cap={cap_pv}")
        if cap_h is not None and h_mw > cap_h + 1e-6:
            warnings.append(f"[{h}] Hidro excede capacidad: usado={h_mw} > cap={cap_h}")
        if cap_t is not None and t_mw > cap_t + 1e-6:
            warnings.append(f"[{h}] Térmica excede capacidad: usado={t_mw} > cap={cap_t}")

        dem_ini = r.get("demanda_inicial", None)
        total = r["total_despachado_mw"]
        if isinstance(dem_ini, (int, float)) and total - dem_ini > 1e-6:
            warnings.append(f"[{h}] Despacho > demanda: total={total} > demanda={dem_ini}")

    return warnings


def evaluate_goal(rows: List[Dict], ultimo_to: Optional[str], params: Dict):
    """
    Evalúa el goal:
      (and (hora_actual h_goal) (< (demanda h_goal) (unidad_despacho)))
    """
    unidad = params["unidad_despacho"]
    # h_goal = última hora definida en demanda
    if params.get("demanda"):
        h_goal = sorted(params["demanda"].keys(), key=hour_key)[-1]
    else:
        h_goal = sorted([r["hora"] for r in rows], key=hour_key)[-1]

    goal_msgs = []
    goal_ok = True

    # 1) hora_actual == h_goal (según último avanzar_hora)
    if ultimo_to is None:
        goal_msgs.append("[Objetivo hora_actual] No se encontró ninguna acción 'avanzar_hora' en el plan.")
        goal_ok = False
    elif ultimo_to != h_goal:
        goal_msgs.append(f"[Objetivo hora_actual] Esperado llegar a {h_goal}, pero el último avanzar_hora llega a {ultimo_to}.")
        goal_ok = False
    else:
        goal_msgs.append(f"[Objetivo hora_actual] OK: última hora alcanzada = {h_goal}.")

    # 2) demanda_residual(h_goal) < unidad_despacho (usando la simulación)
    fila_goal = next((r for r in rows if r["hora"] == h_goal), None)
    if not fila_goal:
        goal_msgs.append(f"[Objetivo demanda] No hay fila de resumen para {h_goal}.")
        goal_ok = False
    else:
        dem_res = fila_goal.get("demanda_residual")
        dem_ini = fila_goal.get("demanda_inicial")
        total = fila_goal.get("total_despachado_mw", 0.0)

        if not isinstance(dem_res, (int, float)):
            goal_msgs.append(f"[Objetivo demanda] No se pudo evaluar demanda en {h_goal}.")
            goal_ok = False
        else:
            if dem_res < unidad - 1e-6:
                goal_msgs.append(f"[Objetivo demanda] OK: demanda_residual={dem_res:.3f} < unidad_despacho={unidad}.")
                if isinstance(dem_ini, (int, float)) and total - dem_ini > 1e-6:
                    goal_msgs.append(f"[Observación] En {h_goal}, despacho > demanda (total={total} > demanda={dem_ini}).")
            else:
                goal_msgs.append(f"[Objetivo demanda] NO OK: demanda_residual={dem_res:.3f} ≥ unidad_despacho={unidad}.")
                goal_ok = False

    return goal_msgs, goal_ok, h_goal


# =========================
# Exportación
# =========================

def export_excel(rows: List[Dict], totals: Dict, out_xlsx: Path):
    if pd is None:
        print("ADVERTENCIA: pandas no disponible; se omite Excel.", file=sys.stderr)
        return
    ensure_results_dir(out_xlsx)

    df = pd.DataFrame(rows)
    tot_df = pd.DataFrame([{
        "pv_mw_total": totals["pv_mw"],
        "hidro_mw_total": totals["hidro_mw"],
        "termica_mw_total": totals["termica_mw"],
        "costo_pv_total": totals["costo_pv"],
        "costo_hidro_total": totals["costo_hidro"],
        "costo_termica_total": totals["costo_termica"],
        "costo_total": totals["costo_pv"] + totals["costo_hidro"] + totals["costo_termica"],
    }])

    with pd.ExcelWriter(out_xlsx, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="resumen_por_hora")
        tot_df.to_excel(writer, index=False, sheet_name="totales")


def export_plots(rows: List[Dict], out_png_dispatch: Path, out_png_cost: Path):
    if plt is None or pd is None:
        print("ADVERTENCIA: matplotlib/pandas no disponible; se omiten gráficas.", file=sys.stderr)
        return
    ensure_results_dir(out_png_dispatch)
    ensure_results_dir(out_png_cost)

    df = pd.DataFrame(rows).copy()
    df["hint"] = df["hora"].str[1:].astype(int)
    df = df.sort_values("hint")

    # Despacho por hora vs demanda
    ax = df.plot(
        x="hint",
        y=["pv_mw", "hidro_mw", "termica_mw"],
        kind="bar",
        stacked=True,
        figsize=(14, 6),
        legend=True
    )
    ax2 = ax.twinx()
    if "demanda_inicial" in df.columns:
        df.plot(x="hint", y="demanda_inicial", ax=ax2, legend=False, linewidth=2)
        ax2.set_ylabel("Demanda [MW]")

    ax.set_xlabel("Hora")
    ax.set_ylabel("Despacho [MW]")
    ax.set_title("Despacho por hora (PV + Hidro + Térmica) vs Demanda")
    ax.set_xticklabels(df["hora"])
    plt.tight_layout()
    plt.savefig(out_png_dispatch, dpi=150)
    plt.close()

    # Costo acumulado
    ax = df.plot(x="hint", y="costo_acumulado", kind="line", figsize=(14, 5), legend=False)
    ax.set_xlabel("Hora")
    ax.set_ylabel("Costo acumulado")
    ax.set_title("Costo acumulado del plan")
    ax.set_xticks(range(len(df)))
    ax.set_xticklabels(df["hora"])
    plt.tight_layout()
    plt.savefig(out_png_cost, dpi=150)
    plt.close()


def export_verification_report(warnings: List[str], goal_msgs: List[str], goal_ok: bool, h_goal: str, out_txt: Path):
    ensure_results_dir(out_txt)
    header = []
    header.append("VERIFICACIÓN DEL GOAL PDDL")
    header.append("--------------------------")
    header.extend(goal_msgs)
    header.append("")
    header.append("VERIFICACIÓN GENERAL")
    header.append("--------------------")
    if warnings:
        header.append(f"Se encontraron {len(warnings)} observación(es):")
    else:
        header.append("Sin observaciones. Todo consistente.")
    body = "\n".join(header + warnings)
    out_txt.write_text(body, encoding="utf-8")


# =========================
# Main
# =========================

def main():
    if len(sys.argv) < 3:
        print("Uso: python scripts/verificar_y_visualizar_plan_priorizado.py <problem.pddl> <plan.txt>", file=sys.stderr)
        sys.exit(2)

    problem_path = Path(sys.argv[1])
    plan_path = Path(sys.argv[2])

    if not problem_path.exists():
        print(f"ERROR: No existe el archivo problem: {problem_path}", file=sys.stderr)
        sys.exit(1)
    if not plan_path.exists():
        print(f"ERROR: No existe el archivo plan: {plan_path}", file=sys.stderr)
        sys.exit(1)

    try:
        params = parse_problem(problem_path)
        markers = parse_plan(plan_path)

        # ---- Simulación (clave) ----
        counts, demanda_final, ultimo_to = simulate_plan(markers, params)

        # Construir resumen a partir de la simulación
        rows, totals = build_summary(counts, demanda_final, params)

        base = os.path.splitext(os.path.basename(plan_path))[0]
        out_dir = plan_path.parent

        out_xlsx = out_dir / f"resumen_{base}.xlsx"
        out_png_dispatch = out_dir / f"grafica_despacho_{base}.png"
        out_png_cost = out_dir / f"grafica_costo_acumulado_{base}.png"
        out_verify = out_dir / f"verificacion_{base}.txt"

        # Exportar tablas y gráficas
        export_excel(rows, totals, out_xlsx)
        export_plots(rows, out_png_dispatch, out_png_cost)

        # Verificación general
        warnings = verify(rows, params)

        # Verificación del GOAL modificado
        goal_msgs, goal_ok, h_goal = evaluate_goal(rows, ultimo_to, params)

        # Reporte de verificación
        export_verification_report(warnings, goal_msgs, goal_ok, h_goal, out_verify)

        # Resumen corto en consola
        total_mw = totals["pv_mw"] + totals["hidro_mw"] + totals["termica_mw"]
        total_cost = totals["costo_pv"] + totals["costo_hidro"] + totals["costo_termica"]
        print("\n====== Resumen rápido ======")
        print(f"Energía total [MW]: {total_mw:,.0f}  (PV={totals['pv_mw']:,.0f}, Hidro={totals['hidro_mw']:,.0f}, Térmica={totals['termica_mw']:,.0f})")
        print(f"Costo total: {total_cost:,.2f}")
        print(f"Goal PDDL (hora={h_goal}): {'OK' if goal_ok else 'NO OK'}  -> ver {out_verify.name}")
        if warnings:
            print(f"Verificación general: {len(warnings)} observación(es). Revisa {out_verify.name}")
        else:
            print("Verificación general: sin observaciones.")
        print(f"Excel:   {out_xlsx}")
        print(f"Gráficas: {out_png_dispatch} | {out_png_cost}")
        print(f"Reporte: {out_verify}\n")

    except Exception as ex:
        print("ERROR durante el procesamiento:", file=sys.stderr)
        print(repr(ex), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
