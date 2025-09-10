# scripts/parse_priorizado_plan_sim.py
# Parser + simulador para ENHSP con dominio "despacho_priorizado"
# Acciones: despachar_pv, marcar_pv_agotado, despachar_hidro, marcar_hidro_agotado,
#           despachar_termica, avanzar_hora
#
# Salida: imprime verificación y crea CSV por hora con despacho por fuente.

import re, sys, csv
from pathlib import Path
from collections import defaultdict

# --------- Regex generales ----------
FLOAT = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'
RE_METRIC = re.compile(r'Metric\s*\(Search\)\s*:\s*(' + FLOAT + r')', re.IGNORECASE)

# Acciones con/sin timestamp "0.0: (act h12 [h13])"
RE_ACT_TS   = re.compile(r'^\s*\d+(?:\.\d+)?:\s*\(([A-Za-z0-9_\-]+)\s+(h\d+)(?:\s+(h\d+))?\)\s*$', re.IGNORECASE)
RE_ACT_NOTS = re.compile(r'^\s*\(([A-Za-z0-9_\-]+)\s+(h\d+)(?:\s+(h\d+))?\)\s*$', re.IGNORECASE)

# --------- Utilidades ----------
def strip_comments(txt: str) -> str:
    return re.sub(r';.*', '', txt)

def parse_hours_from_objects(txt: str):
    m = re.search(r'\(:objects(.*?)-\s*hour\)', txt, flags=re.DOTALL|re.IGNORECASE)
    if not m:
        # fallback sensato
        return list(range(24))
    chunk = m.group(1)
    hrs = sorted({int(n) for n in re.findall(r'\bh(\d+)\b', chunk, flags=re.IGNORECASE)})
    return hrs or list(range(24))

def extract_paren_block(txt: str, anchor: str) -> str:
    """
    Extrae el bloque de paréntesis que empieza EXACTAMENTE en 'anchor'
    (p.ej. '(:init') usando balanceo. Devuelve el substring '(... )' completo.
    """
    i = txt.find(anchor)
    if i < 0:
        return ""
    start = i
    depth = 0
    for k in range(start, len(txt)):
        c = txt[k]
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return txt[start:k+1]
    return ""

def slice_found_plan(plan_text: str) -> str:
    s = plan_text
    i = s.find("Found Plan:")
    if i >= 0:
        s = s[i + len("Found Plan:"):]
        j = s.find("Plan-Length")
        if j >= 0:
            s = s[:j]
    return s

# --------- Parse del problema (solo :init) ----------
def parse_problem(problem_path: Path):
    raw = problem_path.read_text(encoding='utf-8', errors='ignore')
    txt = strip_comments(raw)

    hours = parse_hours_from_objects(txt)

    init_block = extract_paren_block(txt, '(:init')
    if not init_block:
        print("[AVISO] No se pudo aislar el bloque (:init ...). Se intentará parsear todo el archivo.")
    source = init_block if init_block else txt

    scalars = {}
    per_h = defaultdict(lambda: defaultdict(float))

    # (= (fn hN) val)
    for m in re.finditer(r'\(=\s*\(\s*([A-Za-z0-9_]+)\s+(h(\d+))\s*\)\s*(' + FLOAT + r')\s*\)', source):
        fn = m.group(1).lower()
        h  = int(m.group(3))
        val = float(m.group(4))
        per_h[fn][h] = val

    # (= (fn) val)
    for m in re.finditer(r'\(=\s*\(\s*([A-Za-z0-9_]+)\s*\)\s*(' + FLOAT + r')\s*\)', source):
        fn = m.group(1).lower()
        val = float(m.group(2))
        scalars[fn] = val

    # Diagnóstico rápido
    def cnt(name): return len(per_h.get(name, {}))
    sum_dem = sum(per_h['demanda'].values()) if per_h['demanda'] else 0.0
    print(f"[DBG] problem(:init) → hours:{len(hours)}  demanda:{cnt('demanda')} (Σ={sum_dem:,.0f})  "
          f"pv:{cnt('pv_disponible')}  hidro_h:{cnt('hidro_disponible_hora')}  term_h:{cnt('termica_disponible_hora')}")
    if len(per_h['demanda']) != len(hours):
        print("[AVISO] Cantidad de (= (demanda hN) ...) distinta del # de horas.")

    return hours, scalars, per_h

# --------- Parse del plan ----------
def parse_plan(plan_path: Path):
    full_txt = plan_path.read_text(encoding='utf-8', errors='ignore')
    plan_txt = slice_found_plan(full_txt)
    lines = plan_txt.splitlines()

    actions = []
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        m = RE_ACT_TS.match(ln) or RE_ACT_NOTS.match(ln)
        if not m:
            continue
        act = m.group(1).lower()
        h1s = m.group(2).lower()
        h2s = m.group(3).lower() if m.group(3) else None
        try:
            h1 = int(h1s[1:])  # "h12" -> 12
        except:
            continue
        h2 = int(h2s[1:]) if h2s else None
        actions.append((act, h1, h2))

    metric = None
    mm = RE_METRIC.search(full_txt)
    if mm:
        try:
            metric = float(mm.group(1))
        except:
            pass

    print(f"[DBG] Acciones leídas del plan: {len(actions)}")
    if actions:
        print("[DBG] Primeras 6:", actions[:6])
    else:
        print("[AVISO] No se reconocieron acciones. Revisa el archivo de plan o el regex.")

    return actions, metric

# --------- Simulación ----------
def clamp(x, lo=0.0, hi=None):
    if hi is None:
        return max(lo, x)
    return min(max(lo, x), hi)

def simulate(plan_actions, hours, scalars, per_h):
    # Estados por hora (copias)
    demanda   = {h: per_h['demanda'].get(h, 0.0) for h in hours}
    pv_disp   = {h: per_h['pv_disponible'].get(h, 0.0) for h in hours}
    hidro_h   = {h: per_h['hidro_disponible_hora'].get(h, 0.0) for h in hours}
    term_h    = {h: per_h['termica_disponible_hora'].get(h, 0.0) for h in hours}

    # Totales servidos para reporte
    served_pv    = {h: 0.0 for h in hours}
    served_hidro = {h: 0.0 for h in hours}
    served_term  = {h: 0.0 for h in hours}

    # Escalares
    presupuesto = scalars.get('presupuesto_hidro_diario', 0.0)
    unidad      = scalars.get('unidad_despacho', 10.0)
    c_pv        = scalars.get('costo_pv', 0.0)
    c_hidro     = scalars.get('costo_hidro', 0.0)
    c_term      = scalars.get('costo_termica', 0.0)

    warnings = defaultdict(int)
    accum_cost = 0.0

    for (act, h, h2) in plan_actions:
        if h not in demanda:
            continue

        if act == 'despachar_pv':
            x_req = unidad
            x = clamp(x_req, 0, min(demanda[h], pv_disp[h]))
            if abs(x - x_req) > 1e-9:
                warnings['pv_clamped'] += 1
            demanda[h] -= x
            pv_disp[h] -= x
            served_pv[h] += x
            accum_cost  += x * c_pv

        elif act == 'despachar_hidro':
            x_req = unidad
            x = clamp(x_req, 0, min(demanda[h], hidro_h[h], presupuesto))
            if abs(x - x_req) > 1e-9:
                warnings['hidro_clamped'] += 1
            demanda[h] -= x
            hidro_h[h] -= x
            presupuesto -= x
            served_hidro[h] += x
            accum_cost += x * c_hidro

        elif act == 'despachar_termica':
            x_req = unidad
            x = clamp(x_req, 0, min(demanda[h], term_h[h]))
            if abs(x - x_req) > 1e-9:
                warnings['termica_clamped'] += 1
            demanda[h] -= x
            term_h[h] -= x
            served_term[h] += x
            accum_cost += x * c_term

        elif act in ('marcar_pv_agotado', 'marcar_hidro_agotado', 'avanzar_hora'):
            # Acciones de “control” (predicados) sin efecto numérico en el CSV/costos
            pass

        # saneo numérico
        if abs(demanda[h]) < 1e-9:
            demanda[h] = 0.0
        if abs(pv_disp[h]) < 1e-9:
            pv_disp[h] = 0.0
        if abs(hidro_h[h]) < 1e-9:
            hidro_h[h] = 0.0
        if abs(term_h[h]) < 1e-9:
            term_h[h] = 0.0

    # Agregados
    total_pv = sum(served_pv.values())
    total_hy = sum(served_hidro.values())
    total_th = sum(served_term.values())
    total_energy = total_pv + total_hy + total_th

    total_demanda0 = sum(per_h['demanda'].get(h, 0.0) for h in hours)
    remaining = sum(demanda.values())

    cost_break = {
        'pv': total_pv * c_pv,
        'hidro': total_hy * c_hidro,
        'termica': total_th * c_term
    }
    total_cost = sum(cost_break.values())

    return {
        'accum_cost_sim': accum_cost,
        'total_cost_recalc': total_cost,
        'cost_break': cost_break,
        'totals_mwh': {'pv': total_pv, 'hidro': total_hy, 'termica': total_th, 'sum': total_energy},
        'demand': {'initial': total_demanda0, 'remaining': remaining, 'balance': total_energy - total_demanda0},
        'presupuesto_hidro_restante': presupuesto,
        'warnings': dict(warnings),
        'per_hour': {'pv': served_pv, 'hidro': served_hidro, 'termica': served_term},
        'params': {'unidad': unidad, 'costo_pv': c_pv, 'costo_hidro': c_hidro, 'costo_termica': c_term}
    }

# --------- CSV ----------
def save_csv(report, out_csv: Path, hours):
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['hour','pv_mwh','hidro_mwh','termica_mwh'])
        for h in hours:
            w.writerow([h,
                        report['per_hour']['pv'].get(h, 0.0),
                        report['per_hour']['hidro'].get(h, 0.0),
                        report['per_hour']['termica'].get(h, 0.0)])

# --------- main ----------
def main():
    if len(sys.argv) < 3:
        print("Uso: python scripts/parse_priorizado_plan_sim.py <plan.txt> <problem.pddl>")
        sys.exit(1)
    plan_path = Path(sys.argv[1]); problem_path = Path(sys.argv[2])
    if not plan_path.exists():
        print(f"[ERROR] No existe plan: {plan_path}"); sys.exit(2)
    if not problem_path.exists():
        print(f"[ERROR] No existe problema: {problem_path}"); sys.exit(3)

    actions, metric = parse_plan(plan_path)
    hours, scalars, per_h = parse_problem(problem_path)

    report = simulate(actions, hours, scalars, per_h)

    print("\n=== Verificación por simulación (dominio priorizado) ===")
    if metric is not None:
        print(f"Metric (Search) en archivo ENHSP: {metric:,.0f} $")
    print(f"Coste simulado acumulado:        {report['accum_cost_sim']:,.0f} $")
    print(f"Coste recomputado por totales:   {report['total_cost_recalc']:,.0f} $")

    print("\nDemanda total inicial:           {:,.0f} MWh".format(report['demand']['initial']))
    print("Energía servida total:           {:,.0f} MWh".format(report['totals_mwh']['sum']))
    print("Balance (serv - demanda):        {:,.0f} MWh".format(report['demand']['balance']))
    print("Demanda restante (ideal 0):      {:,.0f} MWh".format(report['demand']['remaining']))

    print("\nDesglose MWh:")
    print("  PV      : {:,.0f} MWh".format(report['totals_mwh']['pv']))
    print("  Hidro   : {:,.0f} MWh".format(report['totals_mwh']['hidro']))
    print("  Térmica : {:,.0f} MWh".format(report['totals_mwh']['termica']))

    print("\nDesglose Costes:")
    print("  PV      : ${:,.0f}".format(report['cost_break']['pv']))
    print("  Hidro   : ${:,.0f}".format(report['cost_break']['hidro']))
    print("  Térmica : ${:,.0f}".format(report['cost_break']['termica']))

    print("\nPresupuesto hidro restante (día): {:,.0f} MWh".format(report['presupuesto_hidro_restante']))

    if report['warnings']:
        print("\n[AVISOS] Clamps aplicados en simulación (acciones truncadas por límites):")
        for k, v in report['warnings'].items():
            print(f"  {k}: {v}")

    out_csv = plan_path.parent / 'pddl_dispatch_priorizado_sim.csv'
    save_csv(report, out_csv, hours)
    print(f"\nCSV por hora → {out_csv}")

if __name__ == "__main__":
    main()
