
"""
resumir_plan_priorizado.py

Uso:
  python scripts/resumir_plan_priorizado.py <ruta_problem_pddl> <ruta_plan_txt>

"""

from __future__ import annotations

import re
import sys
import csv
import os
from pathlib import Path
from collections import defaultdict, OrderedDict
from typing import Dict, Tuple, List, Optional

# ==========
# Regex
# ==========

# Acciones del plan: (despachar_pv h10), (marcar_pv_agotado h10), (avanzar_hora h10 h11), ...
RGX_ACTION = re.compile(
    r'\(\s*(?P<action>despachar_(?:pv|hidro|termica)|marcar_(?:pv|hidro)_agotado|avanzar_hora)\s+'
    r'(?P<h1>h\d{1,2})(?:\s+(?P<h2>h\d{1,2}))?\s*\)',
    re.IGNORECASE
)

# Parámetros escalares en el problem
RGX_ESCALAR = {
    "costo_pv": re.compile(r"\(=\s*\(costo_pv\)\s*([+-]?\d+(?:\.\d+)?)\)", re.IGNORECASE),
    "costo_hidro": re.compile(r"\(=\s*\(costo_hidro\)\s*([+-]?\d+(?:\.\d+)?)\)", re.IGNORECASE),
    "costo_termica": re.compile(r"\(=\s*\(costo_termica\)\s*([+-]?\d+(?:\.\d+)?)\)", re.IGNORECASE),
    "unidad_despacho": re.compile(r"\(=\s*\(unidad_despacho\)\s*([+-]?\d+(?:\.\d+)?)\)", re.IGNORECASE),
}

# Series por hora: demanda hX = Y
RGX_DEMANDA = re.compile(r"\(=\s*\(demanda\s+(h\d{1,2})\)\s*([+-]?\d+(?:\.\d+)?)\)", re.IGNORECASE)


# ==========
# Utilidades
# ==========

def hour_key(h: str) -> int:
    """Convierte 'h0' -> 0, 'h12' -> 12 para ordenar correctamente."""
    try:
        return int(h[1:])
    except Exception:
        return 10**9  # por si aparece algo raro


# ==========
# Parseadores
# ==========

def parse_plan(plan_path: Path):
    """
    Devuelve:
      dispatch_counts[hour]['pv'|'hidro'|'termica'] = número de acciones de despacho en esa hora
      markers = lista cruda de (action, h1, h2) por trazabilidad
    """
    text = plan_path.read_text(encoding="utf-8", errors="ignore")
    counts = defaultdict(lambda: defaultdict(int))
    markers: List[Tuple[str, str, Optional[str]]] = []

    for m in RGX_ACTION.finditer(text):
        action = m.group("action").lower()
        h1 = (m.group("h1") or "").lower()
        h2 = (m.group("h2") or None)
        if h2:
            h2 = h2.lower()

        # Contamos solo las acciones de despacho (cada una equivale a "unidad_despacho")
        if action.startswith("despachar_"):
            src = action.split("_", 1)[1]  # pv | hidro | termica
            counts[h1][src] += 1

        markers.append((action, h1, h2))

    return counts, markers


def parse_problem(problem_path: Path):
    """
    Extrae de problem.pddl:
      - unidad_despacho (float)
      - costos por fuente (float)
      - demanda por hora { 'h0': float, ... }
    """
    text = problem_path.read_text(encoding="utf-8", errors="ignore")

    esc: Dict[str, float] = {}
    for key, rgx in RGX_ESCALAR.items():
        m = rgx.search(text)
        if m:
            esc[key] = float(m.group(1))
        else:
            raise ValueError(f"No se encontró el parámetro '{key}' en {problem_path.name}")

    demanda: Dict[str, float] = {}
    for m in RGX_DEMANDA.finditer(text):
        h = m.group(1).lower()
        val = float(m.group(2))
        demanda[h] = val

    if not demanda:
        # No es crítico para el resumen, pero ayuda a calcular residuales.
        print("ADVERTENCIA: No se encontró ninguna '(= (demanda hX) N)' en el problem. "
              "El CSV no tendrá columna de demanda inicial.", file=sys.stderr)

    return {
        "unidad_despacho": esc["unidad_despacho"],
        "costo_pv": esc["costo_pv"],
        "costo_hidro": esc["costo_hidro"],
        "costo_termica": esc["costo_termica"],
        "demanda": demanda,
    }


# ==========
# Lógica de resumen
# ==========

def build_summary(counts, params):
    """
    Construye filas por hora con energía y costo.
    Retorna (rows, totals) donde:
      rows: lista de dicts con columnas para CSV
      totals: dict con totales agregados
    """
    unidad = params["unidad_despacho"]
    c_pv = params["costo_pv"]
    c_h = params["costo_hidro"]
    c_t = params["costo_termica"]
    demanda_map = params.get("demanda", {})

    # Horas = unión de horas vistas en el plan y en la demanda
    horas = set(counts.keys()) | set(demanda_map.keys())
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

        dem_ini = demanda_map.get(h)
        total_mw = pv_mw + h_mw + t_mw
        dem_res = dem_ini - total_mw if dem_ini is not None else None

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

        # Acumular totales
        tot["pv_mw"] += pv_mw
        tot["hidro_mw"] += h_mw
        tot["termica_mw"] += t_mw
        tot["costo_pv"] += costo_pv
        tot["costo_hidro"] += costo_h
        tot["costo_termica"] += costo_t

    return rows, tot


def write_csv(rows: List[Dict], out_path: Path):
    if not rows:
        print("No hay filas que escribir al CSV (¿el plan no tiene acciones?).", file=sys.stderr)
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def pretty_print_totals(tot: Dict, params: Dict):
    unidad = params["unidad_despacho"]
    c_pv = params["costo_pv"]
    c_h = params["costo_hidro"]
    c_t = params["costo_termica"]

    print("\n================= RESUMEN GLOBAL =================")
    print(f"Unidad de despacho: {unidad}")
    print(f"Costos: PV={c_pv}, Hidro={c_h}, Térmica={c_t}\n")

    total_mw = tot["pv_mw"] + tot["hidro_mw"] + tot["termica_mw"]
    total_costo = tot["costo_pv"] + tot["costo_hidro"] + tot["costo_termica"]

    print(f"Energía total despachada [MW]: {total_mw:,.0f}")
    print(f"  - PV:     {tot['pv_mw']:,.0f}")
    print(f"  - Hidro:  {tot['hidro_mw']:,.0f}")
    print(f"  - Térmica:{tot['termica_mw']:,.0f}")
    print()
    print(f"Costo total: {total_costo:,.2f}")
    print(f"  - Costo PV:     {tot['costo_pv']:,.2f}")
    print(f"  - Costo Hidro:  {tot['costo_hidro']:,.2f}")
    print(f"  - Costo Térmica:{tot['costo_termica']:,.2f}")
    print("==================================================\n")


# ==========
# Main
# ==========

def main():
    if len(sys.argv) < 3:
        print("Uso: python scripts/resumir_plan_priorizado.py <problem.pddl> <plan.txt>", file=sys.stderr)
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
        counts, _markers = parse_plan(plan_path)
        rows, tot = build_summary(counts, params)

        # CSV de salida: mismo directorio del plan
        base = os.path.splitext(os.path.basename(plan_path))[0]
        out_csv = plan_path.parent / f"resumen_{base}.csv"

        write_csv(rows, out_csv)
        pretty_print_totals(tot, params)

        print(f"CSV generado: {out_csv}")

    except Exception as ex:
        print("ERROR durante el procesamiento:", file=sys.stderr)
        print(repr(ex), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
