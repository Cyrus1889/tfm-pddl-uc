# Planificación Determinista del Despacho Diario de Energías Renovables mediante PDDL
**Evaluación comparativa de planificadores (PDDL vs. MILP)**  
Autor: **Alejandro Orquera** · Repo: https://github.com/cyrus1889/tfm-pddl-uc

Este repositorio contiene el código, modelos, datos y resultados del Trabajo de Fin de Máster:
**“Planificación Determinista del Despacho Diario de Energías Renovables mediante PDDL: Evaluación Comparativa de Planificadores”.**

El objetivo es comparar un modelo simbólico en **PDDL** (planificador ENHSP) con un modelo **MILP** (Pyomo + solver) en **cuatro escenarios** (caso base + 3 escenarios), usando **los mismos datos y restricciones**. Se evalúan factibilidad/cobertura, costo total, ENS (si aplica) y tiempos de cómputo.

---

## 📁 Estructura del repositorio

```
data_caso_base/       # CSV del caso base (costs, demand_profile, hydro_profile, pv_profile, system_constraints, thermal_profile)
data_escenario1/      # CSV del escenario 1
data_escenario2/      # CSV del escenario 2
data_escenario3/      # CSV del escenario 3

models/
  milp/               # (si se agregan artefactos específicos de MILP)
  pddl_caso_base/     # domain_priorizado(.pddl|2) y problem_priorizado(.pddl|2)
  pddl_escenario1/    # domain_escenario1.pddl, problem_escenario1.pddl
  pddl_escenario2/    # domain_escenario2.pddl, problem_escenario2.pddl
  pddl_escenario3/    # domain_escenario3.pddl, problem_escenario3.pddl

results_caso_base/    # resultados del caso base (MILP y PDDL: CSV/PNG/TXT/XLSX)
results_escenario1/   # resultados del escenario 1
results_escenario2/   # resultados del escenario 2
results_escenario3/   # resultados del escenario 3

scripts/              # Python: MILP (Pyomo), parsers/validación, resúmenes y comparativas
docs/                 # (opcional) requisitos, capturas, notas para la memoria
```

Archivos destacados en `scripts/`:
- `milp_model.py` (modelo MILP en Pyomo)
- `test_milp.py` (prueba/ejecución rápida del MILP)
- `resumir_plan_priorizado.py` (resumen del plan PDDL)
- `verificar_y_visualizar_plan_priorizado.py` (verificación/plots PDDL)
- `comparar_resultados_fase5.py` (comparativa MILP vs PDDL)

---

## 🔧 Requisitos

- **Python** ≥ 3.9  
  Instalación mínima (pip):
  ```bash
  pip install pandas numpy matplotlib pyomo openpyxl
  ```
  *(o usa `docs/requirements.txt` si lo añades: `pip install -r docs/requirements.txt`)*

- **Solver MILP**: GLPK/CBC/Gurobi/CPLEX (configura el que prefieras para Pyomo).
- **Java** (para ejecutar **ENHSP**).
- **ENHSP** (`enhsp.jar`): descargar y colocar el `.jar` accesible desde la consola.

> **Sugerencia (Windows/PowerShell):** crea un entorno virtual
> ```powershell
> py -3.11 -m venv .venv
> .\.venv\Scripts\Activate.ps1
> pip install pandas numpy matplotlib pyomo openpyxl
> ```

---

## ▶️ Ejecución (ejemplos)

### 1) PDDL con ENHSP

**Windows (PowerShell)** — caso base (priorizado2):
```powershell
java -jar enhsp.jar ^
  -o models/pddl_caso_base/domain_priorizado2.pddl ^
  -f models/pddl_caso_base/problem_priorizado2.pddl ^
  -s sat -h hadd
```

**Linux/macOS (bash)** — caso base:
```bash
java -jar enhsp.jar   -o models/pddl_caso_base/domain_priorizado2.pddl   -f models/pddl_caso_base/problem_priorizado2.pddl   -s sat -h hadd
```

Escenarios (Windows/PowerShell; análogo en bash cambiando `^` por `\`):
```powershell
# escenario 1
java -jar enhsp.jar ^
  -o models/pddl_escenario1/domain_escenario1.pddl ^
  -f models/pddl_escenario1/problem_escenario1.pddl ^
  -s sat -h hadd

# escenario 2
java -jar enhsp.jar ^
  -o models/pddl_escenario2/domain_escenario2.pddl ^
  -f models/pddl_escenario2/problem_escenario2.pddl ^
  -s sat -h hadd

# escenario 3
java -jar enhsp.jar ^
  -o models/pddl_escenario3/domain_escenario3.pddl ^
  -f models/pddl_escenario3/problem_escenario3.pddl ^
  -s sat -h hadd
```

**Resumir plan PDDL** (caso base, ejemplo):
```powershell
python scripts/resumir_plan_priorizado.py ^
  models/pddl_caso_base/problem_priorizado2.pddl ^
  "results_caso_base/plan_enhsp_sat_hadd_priorizado2.txt"
```

**Verificar/visualizar plan PDDL** (ajusta rutas internas si aplica):
```powershell
python scripts/verificar_y_visualizar_plan_priorizado.py
```

> En `results_*` encontrarás: `plan_enhsp_*.txt`, `resumen_plan_*.xlsx`, `verificacion_*.txt`,
> y gráficos (`demanda_vs_generacion*.png`, `gen_*_24h.png`, etc.).

---

### 2) MILP (Pyomo)

Ejecución de prueba:
```powershell
python scripts/test_milp.py
```
> Si el script requiere rutas de datos, edítalas dentro del archivo o añade argumentos según tu configuración.

---

### 3) Comparar MILP vs PDDL

**Caso base:**
```powershell
python scripts/comparar_resultados_fase5.py ^
  --milp-dispatch "results_caso_base/milp_dispatch.csv" ^
  --milp-summary  "results_caso_base/milp_summary.csv" ^
  --pddl-xlsx     "results_caso_base/resumen_plan_enhsp_sat_hadd_priorizado2.xlsx" ^
  --pddl-report   "results_caso_base/verificacion_plan_enhsp_sat_hadd_priorizado2.txt" ^
  --outdir        "results_caso_base"
```

(Análogamente para `results_escenario1/`, `results_escenario2/`, `results_escenario3/`.)

---

## 📊 Resultados incluidos

- **MILP**: `milp_dispatch.csv`, `milp_summary.csv`
- **PDDL (ENHSP)**: `plan_enhsp_*.txt`, `resumen_plan_*.xlsx`, `verificacion_*.txt`
- **Comparativas**: `comparativa_fase5*.csv|md` y `comparativa_fase5_por_hora*.csv`
- **Gráficos**: `demanda_vs_generacion*.png`, `gen_milp_24h.png`, `gen_pddl_24h.png`, etc.

---

## 🔁 Reproducibilidad

- Usa **tags** para congelar versiones citables (p. ej., `v1.0`):
  ```bash
  git tag v1.0
  git push origin v1.0
  ```
- (Opcional) publica un **Release** y adjunta el ZIP correspondiente.
- Si manejas archivos grandes en el futuro (>100 MB), usa **Git LFS**:
  ```bash
  git lfs install
  git lfs track "*.csv" "*.xlsx" "*.png" "*.txt"
  git add .gitattributes
  git commit -m "Track large files with Git LFS"
  git push
  ```

---

## 📄 Licencia y citación

- **Licencia**: añade un archivo `LICENSE` (MIT/Apache-2.0/BSD-3, a tu elección).
- **Cita sugerida**:
  > Orquera, A. (2025). *Planificación determinista del despacho diario de energías renovables mediante PDDL: Evaluación comparativa de planificadores* (Repositorio de código). GitHub: cyrus1889/tfm-pddl-uc. Versión `v1.0`.

---

## 🤝 Contacto

- Autor: **Alejandro Orquera**  
- GitHub: **@cyrus1889**
