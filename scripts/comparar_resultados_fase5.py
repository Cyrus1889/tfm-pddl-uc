
"""
USO con archivos del verificador:
  python comparar_resultados_fase5.py \
      --milp-dispatch results/milp_dispatch.csv \
      --milp-summary  results/milp_summary.csv  \
      --pddl-xlsx     results/resumen_plan_enhsp_sat_hadd_priorizado2.xlsx \
      --pddl-report   results/verificacion_plan_enhsp_sat_hadd_priorizado2.txt \
      --outdir        results


"""
import argparse
import os
import sys
import re
from typing import Dict, Optional, Tuple, List

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def df_to_markdown_simple(df: pd.DataFrame) -> str:
    # Simple Markdown table without external 'tabulate' dependency
    cols = list(df.columns)
    lines = []
    # Header
    lines.append("| " + " | ".join(str(c) for c in cols) + " |")
    # Separator
    lines.append("| " + " | ".join("---" for _ in cols) + " |")
    # Rows
    for _, row in df.iterrows():
        cells = []
        for v in row.tolist():
            if isinstance(v, float):
                # Pretty print floats
                cells.append(f"{v:.6g}")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


TOL = 1e-6

# ---------------------------- Utilidades de I/O --------------------------------

def read_csv_safe(path: str) -> pd.DataFrame:
    if not os.path.isfile(path):
        print(f"[ERROR] No se encontró el archivo: {path}", file=sys.stderr)
        sys.exit(1)
    try:
        return pd.read_csv(path)
    except Exception as e:
        print(f"[ERROR] Falló la lectura CSV ({path}): {e}", file=sys.stderr)
        sys.exit(1)

def read_excel_safe(path: str) -> Dict[str, pd.DataFrame]:
    if not os.path.isfile(path):
        print(f"[ERROR] No se encontró el archivo: {path}", file=sys.stderr)
        sys.exit(1)
    try:
        return pd.read_excel(path, sheet_name=None)  # todas las hojas
    except Exception as e:
        print(f"[ERROR] Falló la lectura Excel ({path}): {e}", file=sys.stderr)
        sys.exit(1)

def read_text_safe(path: str) -> str:
    if not os.path.isfile(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""

def copy_if_exists(src: str, dst_dir: str, new_name: Optional[str] = None) -> Optional[str]:
    if not os.path.isfile(src):
        return None
    try:
        import shutil
        os.makedirs(dst_dir, exist_ok=True)
        basename = new_name if new_name else os.path.basename(src)
        dst = os.path.join(dst_dir, basename)
        # Evitar intentar copiar si ya es el mismo archivo
        if os.path.abspath(src) == os.path.abspath(dst):
            return dst
        shutil.copyfile(src, dst)
        return dst
    except Exception as e:
        print(f"[WARN] No se pudo copiar {src} → {dst_dir}: {e}", file=sys.stderr)
        return None

# ---------------------- Detección flexible de columnas -------------------------

def _lower_cols(df: pd.DataFrame) -> Dict[str, str]:
    return {str(c).lower().strip(): c for c in df.columns}

def guess_columns(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    cols_map = _lower_cols(df)

    def find_any(keys: List[str]) -> Optional[str]:
        for k in keys:
            for lc, orig in cols_map.items():
                if k in lc:
                    return orig
        return None

    pv_col = find_any(["pv", "solar", "fotovolta"])
    hidro_col = find_any(["hidro", "hydro", "hidrául", "hidraul"])
    termica_col = find_any(["térmi", "termic", "thermal", "gas", "diesel", "fossil"])
    demanda_col = find_any(["demanda", "demand", "load"])
    # hora: suelen venir como "h0, h1..." o una columna "hora"
    hora_col = find_any(["hora", "hour", "time", "tiempo", "period", "index", "h0"])
    pv_avail_col = find_any(["pv_avail", "pv-available", "pv_max", "pv cap", "pvcap", "pv_av"])

    return {
        "pv": pv_col,
        "hidro": hidro_col,
        "termica": termica_col,
        "demanda": demanda_col,
        "hora": hora_col,
        "pv_available": pv_avail_col,
    }

# -------------------------- Extracción desde Excel PDDL ------------------------

def _score_dispatch_like(df: pd.DataFrame) -> int:
    guessed = guess_columns(df)
    score = 0
    for k in ["pv", "hidro", "termica", "demanda"]:
        if guessed[k] is not None:
            score += 1
    if len(df) >= 24:
        score += 1
    return score

def try_extract_pddl_dispatch_from_excel(xls: Dict[str, pd.DataFrame]) -> Tuple[Optional[pd.DataFrame], str]:
    best_df = None
    best_name = ""
    best_score = -1
    for name, df in xls.items():
        if not isinstance(df, pd.DataFrame) or df.empty:
            continue
        score = _score_dispatch_like(df)
        if score > best_score:
            best_score = score
            best_df = df
            best_name = name
    if best_df is None or best_score < 2:
        return None, ""
    return best_df, best_name

def try_extract_pddl_summary_from_excel(xls: Dict[str, pd.DataFrame]) -> Dict[str, Optional[float]]:
    keys_cost = ["costo_total", "total_cost", "coste_total", "objective", "obj", "obj_value", "objective_value", "total-cost"]
    keys_time = ["runtime_s", "time_s", "solve_time", "walltime", "seconds", "tiempo", "duración"]
    # 1) intento directo: hoja con columnas clave
    for name, df in xls.items():
        if not isinstance(df, pd.DataFrame) or df.empty:
            continue
        try:
            df_l = df.copy()
            df_l.columns = [str(c).lower().strip() for c in df_l.columns]
            if len(df_l) >= 1:
                row = df_l.iloc[0].to_dict()
                cost = None
                runtime = None
                for k in keys_cost:
                    if k in row:
                        try:
                            cost = float(str(row[k]).replace(",", "").replace(" ", ""))
                            break
                        except Exception:
                            pass
                for k in keys_time:
                    if k in row:
                        try:
                            runtime = float(str(row[k]).replace(",", "").replace(" ", ""))
                            break
                        except Exception:
                            pass
                if cost is not None or runtime is not None:
                    return {"costo_total": cost, "runtime_s": runtime}
            # 2) clave-valor en dos columnas
            if df_l.shape[1] >= 2:
                cost = None
                runtime = None
                for _, r in df_l.iterrows():
                    k = str(r.iloc[0]).lower()
                    v = r.iloc[1]
                    if any(kk in k for kk in keys_cost):
                        try:
                            cost = float(str(v).replace(",", "").replace(" ", ""))
                        except Exception:
                            pass
                    if any(kk in k for kk in keys_time):
                        try:
                            runtime = float(str(v).replace(",", "").replace(" ", ""))
                        except Exception:
                            pass
                if cost is not None or runtime is not None:
                    return {"costo_total": cost, "runtime_s": runtime}
        except Exception:
            continue
    # 3) fallback: buscar una columna de "costo acumulado" y tomar el último valor
    for name, df in xls.items():
        try:
            cols = _lower_cols(df)
            cost_col = None
            for lc, orig in cols.items():
                if "costo" in lc and ("acum" in lc or "acumul" in lc or "acumulado" in lc or "cumulative" in lc):
                    cost_col = orig
                    break
            if cost_col:
                series = pd.to_numeric(df[cost_col], errors="coerce").dropna()
                if not series.empty:
                    cost_total = float(series.iloc[-1])
                    return {"costo_total": cost_total, "runtime_s": None}
        except Exception:
            continue
    return {"costo_total": None, "runtime_s": None}

# -------------------------- Extracción desde Reporte TXT -----------------------

def extract_summary_from_report_txt(txt: str) -> Dict[str, Optional[float]]:
    cost = None
    runtime = None
    patterns_cost = [
        r"total[-_\s]?cost\s*[:=]\s*([0-9]+(?:[\.,][0-9]+)?)",
        r"objective(?:\s+value)?\s*[:=]\s*([0-9]+(?:[\.,][0-9]+)?)",
        r"costo\s*total\s*[:=]\s*([0-9]+(?:[\.,][0-9]+)?)",
        r"costo\s*acumulado\s*[:=]\s*([0-9]+(?:[\.,][0-9]+)?)",
    ]
    for pat in patterns_cost:
        m = re.search(pat, txt, re.IGNORECASE)
        if m:
            try:
                cost = float(m.group(1).replace(",", "."))
                break
            except Exception:
                pass
    patterns_time = [
        r"(?:runtime|solve\s*time|tiempo)\s*[:=]\s*([0-9]+(?:[\.,][0-9]+)?)\s*s",
        r"(?:runtime|solve\s*time|tiempo)\s*[:=]\s*([0-9]+(?:[\.,][0-9]+)?)",
    ]
    for pat in patterns_time:
        m = re.search(pat, txt, re.IGNORECASE)
        if m:
            try:
                runtime = float(m.group(1).replace(",", "."))
                break
            except Exception:
                pass
    return {"costo_total": cost, "runtime_s": runtime}

# ----------------------------- Métricas por caso -------------------------------

def compute_dispatch_metrics(df: pd.DataFrame, label: str) -> Tuple[Dict[str, float], pd.DataFrame]:
    cols = guess_columns(df)
    for tech in ["pv", "hidro", "termica", "demanda"]:
        if cols[tech] is None and tech != "termica":
            print(f"[WARN] '{label}': No se detectó columna para '{tech}'. Se asume 0.", file=sys.stderr)
    n = len(df)
    if n == 0:
        raise ValueError(f"{label}: DataFrame vacío para métricas de despacho.")
    hora = df[cols["hora"]] if (cols["hora"] and cols["hora"] in df.columns) else pd.Series(range(n), name="hora")
    std = pd.DataFrame({
        "hora": hora,
        "pv": df[cols["pv"]].fillna(0.0) if cols["pv"] in df.columns else  pd.Series(np.zeros(n)),
        "hidro": df[cols["hidro"]].fillna(0.0) if cols["hidro"] in df.columns else pd.Series(np.zeros(n)),
        "termica": df[cols["termica"]].fillna(0.0) if (cols["termica"] and cols["termica"] in df.columns) else pd.Series(np.zeros(n)),
        "demanda": df[cols["demanda"]].fillna(0.0) if cols["demanda"] in df.columns else pd.Series(np.zeros(n))
    })
    # Normalizar hora estilo h0..h23 a 0..23 para el eje x de líneas
    try:
        std["hora_num"] = std["hora"].astype(str).str.replace("h", "", case=False).astype(float)
    except Exception:
        std["hora_num"] = pd.to_numeric(std["hora"], errors="coerce").fillna(range(n)).astype(float)
    std["gen_total"] = std[["pv", "hidro", "termica"]].sum(axis=1)
    cobertura_ok = (std["gen_total"] - std["demanda"]).abs() <= TOL
    coverage_pct = 100.0 * (cobertura_ok.sum() / max(1, len(std)))
    total_gen_sum = std["gen_total"].sum()
    pct_renovables = 0.0
    if total_gen_sum > 0:
        pct_renovables = 100.0 * (std["pv"].sum() + std["hidro"].sum()) / total_gen_sum
    # PV curtailment si hay disponibilidad
    pv_curtailment_mwh = 0.0
    cols_map = _lower_cols(df)
    for lc, orig in cols_map.items():
        if any(s in lc for s in ["pv_avail", "pv-available", "pv_max", "pv cap", "pvcap", "pv_av"]):
            pv_av = pd.to_numeric(df[orig], errors="coerce").fillna(0.0).values
            pv_used = std["pv"].values
            pv_curtailment_mwh = float(np.maximum(pv_av - pv_used, 0.0).sum())
            break
    return {
        "coverage_pct": float(coverage_pct),
        "pct_renovables": float(pct_renovables),
        "pv_curtailment_mwh": float(pv_curtailment_mwh),
    }, std

# ------------------------------- Gráficos --------------------------------------

def plot_stack_technologies(std: pd.DataFrame, title: str, outpath: str) -> None:
    plt.figure()
    x = std["hora_num"].values if "hora_num" in std else np.arange(len(std))
    pv = np.maximum(std["pv"].values, 0.0)
    hidro = np.maximum(std["hidro"].values, 0.0)
    termica = np.maximum(std["termica"].values, 0.0)
    plt.stackplot(x, pv, hidro, termica, labels=["PV", "Hidro", "Térmica"])
    plt.title(title)
    plt.xlabel("Hora")
    plt.ylabel("Potencia / Energía (unid.)")
    plt.legend(loc="best")
    plt.tight_layout()
    plt.savefig(outpath, dpi=200)
    plt.close()

def plot_demand_vs_generation(std_milp: pd.DataFrame, std_pddl: pd.DataFrame, outpath: str) -> None:
    plt.figure()
    x = std_milp["hora_num"].values if "hora_num" in std_milp else np.arange(len(std_milp))

    def _valid(y):
        y = np.asarray(y, dtype=float)
        return np.any(np.isfinite(y)) and not np.all(np.isclose(y, 0.0, atol=1e-12))

    # Demanda: priorizar MILP; si no existe o es todo ceros, usar PDDL
    demanda_series = None
    if "demanda" in std_milp and _valid(std_milp["demanda"].values):
        demanda_series = std_milp["demanda"].values
        demanda_label = "Demanda (MILP)"
    elif "demanda" in std_pddl and len(std_pddl) == len(std_milp) and _valid(std_pddl["demanda"].values):
        demanda_series = std_pddl["demanda"].values
        demanda_label = "Demanda (PDDL)"

    if demanda_series is not None:
        plt.plot(x, demanda_series, label=demanda_label)

    # Generación total MILP
    if "gen_total" in std_milp and _valid(std_milp["gen_total"].values):
        plt.plot(x, std_milp["gen_total"].values, label="Generación total (MILP)")

    # Generación total PDDL
    if len(std_pddl) == len(std_milp) and "gen_total" in std_pddl and _valid(std_pddl["gen_total"].values):
        plt.plot(x, std_pddl["gen_total"].values, label="Generación total (PDDL)")

    plt.title("Demanda vs Generación total")
    plt.xlabel("Hora")
    plt.ylabel("Potencia / Energía (unid.)")
    plt.legend(loc="best")
    plt.tight_layout()
    plt.savefig(outpath, dpi=200)
    plt.close()

# ------------------------------- Principal -------------------------------------

def extract_summary_metrics_from_df(df: pd.DataFrame) -> Dict[str, Optional[float]]:
    """Permisivo para CSV de summary (MILP o PDDL)."""
    if len(df) >= 1:
        row = df.iloc[0].to_dict()
        row_lower = {str(k).lower(): row[k] for k in row}
        keys_cost = ["costo_total", "total_cost", "coste_total", "objective", "obj", "obj_value", "objective_value", "total-cost"]
        keys_time = ["runtime_s", "time_s", "solve_time", "walltime", "seconds"]
        cost = None
        for k in keys_cost:
            if k in row_lower:
                try:
                    cost = float(str(row_lower[k]).replace(",", "").replace(" ", ""))
                    break
                except Exception:
                    pass
        runtime = None
        for k in keys_time:
            if k in row_lower:
                try:
                    runtime = float(str(row_lower[k]).replace(",", "").replace(" ", ""))
                    break
                except Exception:
                    pass
        if cost is None:
            for k in row_lower:
                if "cost" in k:
                    try:
                        cost = float(str(row_lower[k]).replace(",", "").replace(" ", ""))
                        break
                    except Exception:
                        pass
        return {"costo_total": cost, "runtime_s": runtime}
    return {"costo_total": None, "runtime_s": None}

def main():
    parser = argparse.ArgumentParser(description="Comparar resultados MILP vs PDDL (FASE 5)")
    parser.add_argument("--milp-dispatch", required=True, help="CSV de despacho MILP (por hora)")
    parser.add_argument("--milp-summary", required=True, help="CSV de resumen MILP")
    # PDDL: opción A (CSV) o B (Excel + Reporte)
    parser.add_argument("--pddl-dispatch", required=False, help="CSV de despacho PDDL/ENHSP (por hora)")
    parser.add_argument("--pddl-summary", required=False, help="CSV de resumen PDDL/ENHSP")
    parser.add_argument("--pddl-xlsx", required=False, help="Excel resumen del verificador ENHSP")
    parser.add_argument("--pddl-report", required=False, help="Reporte TXT del verificador ENHSP")
    parser.add_argument("--outdir", default="results", help="Carpeta de salida para tablas y gráficos")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    # ---------------- MILP ----------------
    milp_dispatch = read_csv_safe(args.milp_dispatch)
    milp_summary_df = read_csv_safe(args.milp_summary)
    milp_summary = extract_summary_metrics_from_df(milp_summary_df)
    milp_metrics, milp_std = compute_dispatch_metrics(milp_dispatch, "MILP")

    # ---------------- PDDL ----------------
    pddl_metrics_dict = None
    pddl_std = None
    pddl_summary = {"costo_total": None, "runtime_s": None}

    used_excel_sheet = ""
    debug_lines = []

    if args.pddl_dispatch and args.pddl_summary:
        # Modo A: CSV directos
        pddl_dispatch_df = read_csv_safe(args.pddl_dispatch)
        pddl_metrics_dict, pddl_std = compute_dispatch_metrics(pddl_dispatch_df, "PDDL")
        pddl_summary = extract_summary_metrics_from_df(read_csv_safe(args.pddl_summary))
        debug_lines.append("PDDL: modo CSV (dispatch+summary).")
    else:
        # Modo B: Excel (+ opcional TXT)
        if not args.pddl_xlsx:
            print("[ERROR] Debe proporcionar --pddl-dispatch y --pddl-summary, o bien --pddl-xlsx.", file=sys.stderr)
            sys.exit(1)
        xls = read_excel_safe(args.pddl_xlsx)
        dispatch_df, used_excel_sheet = try_extract_pddl_dispatch_from_excel(xls)
        if dispatch_df is None:
            print("[ERROR] No se pudo encontrar una hoja con despacho horario en el Excel PDDL.", file=sys.stderr)
            sys.exit(1)
        pddl_metrics_dict, pddl_std = compute_dispatch_metrics(dispatch_df, "PDDL")
        pddl_summary = try_extract_pddl_summary_from_excel(xls)
        if (pddl_summary.get("costo_total") is None or pddl_summary.get("runtime_s") is None) and args.pddl_report:
            txt = read_text_safe(args.pddl_report)
            rep_metrics = extract_summary_from_report_txt(txt)
            for k in ["costo_total", "runtime_s"]:
                if pddl_summary.get(k) is None and rep_metrics.get(k) is not None:
                    pddl_summary[k] = rep_metrics[k]
        debug_lines.append(f"PDDL: modo Excel. Hoja despacho usada: '{used_excel_sheet}'. Resumen: {pddl_summary}")

        # Intento enlazar PNGs del verificador
        xlsx_dir = os.path.dirname(os.path.abspath(args.pddl_xlsx))
        cand1 = None
        cand2 = None
        # buscar por patrones comunes
        for fname in os.listdir(xlsx_dir):
            fl = fname.lower()
            if "grafica_despacho" in fl and fl.endswith(".png"):
                cand1 = os.path.join(xlsx_dir, fname)
            if "grafica_costo" in fl and fl.endswith(".png"):
                cand2 = os.path.join(xlsx_dir, fname)
        pddl_plot_despacho = copy_if_exists(cand1, args.outdir, "pddl_grafica_despacho_original.png") if cand1 else None
        pddl_plot_costo = copy_if_exists(cand2, args.outdir, "pddl_grafica_costo_acumulado_original.png") if cand2 else None

    # --- Gap relativo de coste ---
    gap_cost = None
    if milp_summary["costo_total"] is not None and pddl_summary["costo_total"] is not None and milp_summary["costo_total"] != 0:
        gap_cost = (pddl_summary["costo_total"] - milp_summary["costo_total"]) / abs(milp_summary["costo_total"])

    # --- Guardar comparativa CSV ---
    comp_rows = [{
        "enfoque": "MILP",
        "costo_total": milp_summary["costo_total"],
        "tiempo_s": milp_summary["runtime_s"],
        "demanda_cubierta_pct": milp_metrics["coverage_pct"],
        "porcentaje_renovables_pct": milp_metrics["pct_renovables"],
        "pv_no_utilizada_mwh": milp_metrics["pv_curtailment_mwh"]
    },{
        "enfoque": "PDDL",
        "costo_total": pddl_summary["costo_total"],
        "tiempo_s": pddl_summary["runtime_s"],
        "demanda_cubierta_pct": pddl_metrics_dict["coverage_pct"],
        "porcentaje_renovables_pct": pddl_metrics_dict["pct_renovables"],
        "pv_no_utilizada_mwh": pddl_metrics_dict["pv_curtailment_mwh"]
    }]
    comp_df = pd.DataFrame(comp_rows)
    out_csv = os.path.join(args.outdir, "comparativa_fase5.csv")
    comp_df.to_csv(out_csv, index=False)

    # Extra: diferencias por hora entre enfoques
    try:
        merged = pd.DataFrame({
            'hora': milp_std['hora'],
            'milp_gen_total': milp_std['gen_total'],
            'pddl_gen_total': pddl_std['gen_total'] if len(pddl_std)==len(milp_std) else np.nan,
        })
        if 'demanda' in milp_std:
            merged['demanda'] = milp_std['demanda']
        elif 'demanda' in pddl_std and len(pddl_std)==len(milp_std):
            merged['demanda'] = pddl_std['demanda']
        merged['diff_gen_total'] = merged['pddl_gen_total'] - merged['milp_gen_total']
        merged.to_csv(os.path.join(args.outdir, 'comparativa_fase5_por_hora.csv'), index=False)
    except Exception as e:
        print(f"[WARN] No se pudo generar comparativa por hora: {e}", file=sys.stderr)


    # --- Gráficos generados por este comparador ---
    out_png_milp = os.path.join(args.outdir, "gen_milp_24h.png")
    out_png_pddl = os.path.join(args.outdir, "gen_pddl_24h.png")
    out_png_dvg = os.path.join(args.outdir, "demanda_vs_generacion.png")
    try:
        plot_stack_technologies(milp_std, "Generación por tecnología (MILP)", out_png_milp)
    except Exception as e:
        print(f"[WARN] No se pudo generar gráfico MILP: {e}", file=sys.stderr)
    try:
        plot_stack_technologies(pddl_std, "Generación por tecnología (PDDL)", out_png_pddl)
    except Exception as e:
        print(f"[WARN] No se pudo generar gráfico PDDL: {e}", file=sys.stderr)
    try:
        plot_demand_vs_generation(milp_std, pddl_std, out_png_dvg)
    except Exception as e:
        print(f"[WARN] No se pudo generar gráfico Demanda vs Generación: {e}", file=sys.stderr)

    # --- Markdown resumen ---
    out_md = os.path.join(args.outdir, "comparativa_fase5.md")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("# FASE 5 — Comparativa MILP vs PDDL/ENHSP\n\n")
        f.write("## Resumen de métricas\n\n")
        f.write(df_to_markdown_simple(comp_df))
        f.write("\n\n")
        if gap_cost is not None:
            f.write(f"**Gap relativo de coste (PDDL vs MILP)**: {gap_cost:.4%}\n\n")
        else:
            f.write("**Gap relativo de coste (PDDL vs MILP)**: N/D\n\n")
        f.write("## Gráficas generadas por el comparador\n\n")
        f.write(f"- MILP: `gen_milp_24h.png`\n")
        f.write(f"- PDDL: `gen_pddl_24h.png`\n")
        f.write(f"- Demanda vs Generación: `demanda_vs_generacion.png`\n\n")
        # Si existen las PNG originales del verificador, referenciarlas
        if 'pddl_plot_despacho' in locals() and pddl_plot_despacho:
            f.write("## Gráficas originales del verificador (PDDL)\n\n")
            f.write(f"- Despacho (original): `{os.path.basename(pddl_plot_despacho)}`\n")
        if 'pddl_plot_costo' in locals() and pddl_plot_costo:
            f.write(f"- Costo acumulado (original): `{os.path.basename(pddl_plot_costo)}`\n")
        if used_excel_sheet:
            f.write(f"\n\n*Hoja Excel utilizada para PDDL:* **{used_excel_sheet}**\n")
    # --- Archivo debug (útil para trazabilidad en TFM) ---
    debug_path = os.path.join(args.outdir, "comparativa_fase5_debug.txt")
    with open(debug_path, "w", encoding="utf-8") as f:
        f.write("\n".join(debug_lines))

    # --- Mensaje final ---
    print("[OK] Comparativa FASE 5 completada.")
    print(f" - Tabla CSV: {out_csv}")
    print(f" - Tabla MD : {out_md}")
    print(f" - Gráficos : {out_png_milp}, {out_png_pddl}, {out_png_dvg}")
    if gap_cost is not None:
        print(f" - Gap relativo de coste (PDDL vs MILP): {gap_cost:.4%}")
    else:
        print(" - Gap relativo de coste: N/D")


if __name__ == "__main__":
    main()
