"""
Uso:
  python scripts/milp_model.py
  (Opcional) python scripts/milp_model.py --data-dir data --results-dir results --solver glpk

"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import pandas as pd
import pyomo.environ as pyo


def _read_csvs(data_dir: Path):
    demand = pd.read_csv(data_dir / "demand_profile.csv")
    pv = pd.read_csv(data_dir / "pv_profile.csv")
    hydro = pd.read_csv(data_dir / "hydro_profile.csv")
    thermal = pd.read_csv(data_dir / "thermal_profile.csv")
    costs = pd.read_csv(data_dir / "costs.csv")
    constraints = pd.read_csv(data_dir / "system_constraints.csv")

    # Normalizar columnas esperadas
    demand = demand.rename(columns={
        **{c: c.strip() for c in demand.columns}
    })
    pv = pv.rename(columns={
        **{c: c.strip() for c in pv.columns}
    })
    hydro = hydro.rename(columns={
        **{c: c.strip() for c in hydro.columns}
    })
    thermal = thermal.rename(columns={
        **{c: c.strip() for c in thermal.columns}
    })
    costs = costs.rename(columns={
        **{c: c.strip() for c in costs.columns}
    })
    constraints = constraints.rename(columns={
        **{c: c.strip() for c in constraints.columns}
    })

    # Validaciones básicas
    for df, req_cols in [
        (demand, {"hour", "demand_MW"}),
        (pv, {"hour", "pv_avail_MW"}),
        (hydro, {"hour", "hydro_max_MW"}),
        (thermal, {"hour", "thermal_max_MW"}),
    ]:
        miss = req_cols - set(df.columns)
        if miss:
            raise ValueError(f"CSV columns missing in {df}: {miss}")

    # Mapas por hora
    hours = sorted(demand["hour"].astype(int).tolist())
    if hours != list(range(24)):
        raise ValueError("Se esperan horas 0..23 en demand_profile.csv")

    demand_map = dict(zip(demand["hour"].astype(int), demand["demand_MW"].astype(float)))
    pv_map = dict(zip(pv["hour"].astype(int), pv["pv_avail_MW"].astype(float)))
    hydro_map = dict(zip(hydro["hour"].astype(int), hydro["hydro_max_MW"].astype(float)))
    thermal_map = dict(zip(thermal["hour"].astype(int), thermal["thermal_max_MW"].astype(float)))

    # Costos
    cost_map = {row["technology"].strip().lower(): float(row["cost_usd_per_mwh"]) for _, row in costs.iterrows()}
    cost_pv = cost_map.get("pv", 5.0)
    cost_hydro = cost_map.get("hydro", 10.0)
    cost_thermal = cost_map.get("thermal", 90.0)

    # Restricciones del sistema (clave/valor)
    constraint_map = {str(row["key"]).strip(): float(row["value"]) for _, row in constraints.iterrows()}
    hydro_budget = constraint_map.get("hydro_energy_budget_MWh", None)  # None => sin tope energético
    ramp_th = constraint_map.get("thermal_ramp_MW_per_h", None)
    ramp_hy = constraint_map.get("hydro_ramp_MW_per_h", None)

    return hours, demand_map, pv_map, hydro_map, thermal_map, (cost_pv, cost_hydro, cost_thermal), (hydro_budget, ramp_th, ramp_hy)


def build_model(hours, demand_map, pv_map, hydro_map, thermal_map, costs, sys_constraints):
    cost_pv, cost_hydro, cost_thermal = costs
    hydro_budget, ramp_th, ramp_hy = sys_constraints

    m = pyo.ConcreteModel(name="DailyEconomicDispatch")

    # Sets
    m.T = pyo.Set(initialize=hours, ordered=True)

    # Params
    m.demand = pyo.Param(m.T, initialize=demand_map, within=pyo.NonNegativeReals)
    m.pv_avail = pyo.Param(m.T, initialize=pv_map, within=pyo.NonNegativeReals)
    m.hydro_max = pyo.Param(m.T, initialize=hydro_map, within=pyo.NonNegativeReals)
    m.thermal_max = pyo.Param(m.T, initialize=thermal_map, within=pyo.NonNegativeReals)

    m.cost_pv = pyo.Param(initialize=float(cost_pv))
    m.cost_hydro = pyo.Param(initialize=float(cost_hydro))
    m.cost_thermal = pyo.Param(initialize=float(cost_thermal))

    # Vars (MW)
    m.P_pv = pyo.Var(m.T, domain=pyo.NonNegativeReals)
    m.P_hydro = pyo.Var(m.T, domain=pyo.NonNegativeReals)
    m.P_thermal = pyo.Var(m.T, domain=pyo.NonNegativeReals)

    # Capacity constraints
    def pv_cap_rule(m, t):      return m.P_pv[t] <= m.pv_avail[t]
    def hydro_cap_rule(m, t):   return m.P_hydro[t] <= m.hydro_max[t]
    def thermal_cap_rule(m, t): return m.P_thermal[t] <= m.thermal_max[t]
    m.pv_cap = pyo.Constraint(m.T, rule=pv_cap_rule)
    m.hydro_cap = pyo.Constraint(m.T, rule=hydro_cap_rule)
    m.thermal_cap = pyo.Constraint(m.T, rule=thermal_cap_rule)

    # Power balance (>= to allow curtailment? Here we enforce equality to meet demand exactly)
    def balance_rule(m, t):
        return m.P_pv[t] + m.P_hydro[t] + m.P_thermal[t] == m.demand[t]
    m.balance = pyo.Constraint(m.T, rule=balance_rule)

    # Hydro daily energy budget (MWh over 24h). With 1h steps, sum MW == MWh.
    if hydro_budget is not None:
        m.hydro_energy_budget = pyo.Constraint(expr=sum(m.P_hydro[t] for t in m.T) <= hydro_budget)

    # Ramps (MW/h) for thermal and hydro (symmetric up/down)
    # Note: For t0 we skip since no previous hour in horizon. If initial condition known, add it as a Param.
    if ramp_th is not None and ramp_th >= 0:
        def th_ramp_up(m, t):
            if t == hours[0]: return pyo.Constraint.Skip
            return m.P_thermal[t] - m.P_thermal[t-1] <= ramp_th
        def th_ramp_down(m, t):
            if t == hours[0]: return pyo.Constraint.Skip
            return m.P_thermal[t-1] - m.P_thermal[t] <= ramp_th
        m.th_ramp_up = pyo.Constraint(m.T, rule=th_ramp_up)
        m.th_ramp_down = pyo.Constraint(m.T, rule=th_ramp_down)

    if ramp_hy is not None and ramp_hy >= 0:
        def hy_ramp_up(m, t):
            if t == hours[0]: return pyo.Constraint.Skip
            return m.P_hydro[t] - m.P_hydro[t-1] <= ramp_hy
        def hy_ramp_down(m, t):
            if t == hours[0]: return pyo.Constraint.Skip
            return m.P_hydro[t-1] - m.P_hydro[t] <= ramp_hy
        m.hy_ramp_up = pyo.Constraint(m.T, rule=hy_ramp_up)
        m.hy_ramp_down = pyo.Constraint(m.T, rule=hy_ramp_down)

    # Objective (min total cost)
    def total_cost_rule(m):
        return sum(m.P_pv[t]*m.cost_pv + m.P_hydro[t]*m.cost_hydro + m.P_thermal[t]*m.cost_thermal for t in m.T)
    m.total_cost = pyo.Objective(rule=total_cost_rule, sense=pyo.minimize)

    return m


def solve_and_export(model: pyo.ConcreteModel, results_dir: Path, solver_name: str = "glpk", glpk_executable: str | None = None) -> dict:
    results_dir.mkdir(parents=True, exist_ok=True)
    if solver_name.lower() == 'glpk':
        solver = pyo.SolverFactory('glpk', executable=glpk_executable)
    else:
        solver = pyo.SolverFactory(solver_name)
    res = solver.solve(model, tee=False)

    # Extract solution
    hours = list(model.T.data())
    rows = []
    for t in hours:
        rows.append({
            "hour": t,
            "PV_gen_MW": pyo.value(model.P_pv[t]),
            "Hydro_gen_MW": pyo.value(model.P_hydro[t]),
            "Thermal_gen_MW": pyo.value(model.P_thermal[t]),
            "Demand_MW": pyo.value(model.demand[t])
        })
    df = pd.DataFrame(rows).sort_values("hour")
    df.to_csv(results_dir / "milp_dispatch.csv", index=False)

    summary = {
        "solver_status": str(res.solver.status) if hasattr(res, "solver") else "unknown",
        "termination_condition": str(res.solver.termination_condition) if hasattr(res, "solver") else "unknown",
        "total_cost_usd": float(pyo.value(model.total_cost))
    }
    pd.DataFrame([summary]).to_csv(results_dir / "milp_summary.csv", index=False)
    return summary


def main():
    parser = argparse.ArgumentParser(description="Daily Economic Dispatch MILP (Pyomo+GLPK)")
    parser.add_argument("--data-dir", type=str, default=None, help="Ruta a la carpeta data/")
    parser.add_argument("--results-dir", type=str, default=None, help="Ruta a la carpeta results/")
    parser.add_argument("--solver", type=str, default="glpk", help="Nombre de solver Pyomo (glpk, cbc, gurobi, etc.)")
    parser.add_argument("--glpk-exe", type=str, default=r"C:\Anaconda3\envs\tfm_env\Library\bin\glpsol.exe", help="Ruta a glpsol.exe en Windows (GLPK)")
    args = parser.parse_args()

    # Resolve default paths relative to repo root (scripts/..)
    here = Path(__file__).resolve()
    repo_root = here.parent.parent
    data_dir = Path(args.data_dir) if args.data_dir else (repo_root / "data")
    results_dir = Path(args.results_dir) if args.results_dir else (repo_root / "results")

    hours, demand_map, pv_map, hydro_map, thermal_map, costs, sys_constraints = _read_csvs(data_dir)
    model = build_model(hours, demand_map, pv_map, hydro_map, thermal_map, costs, sys_constraints)
    summary = solve_and_export(model, results_dir, solver_name=args.solver, glpk_executable=args.glpk_exe)

    print("=== MILP solved ===")
    print(f"Total cost [USD]: {summary['total_cost_usd']:.2f}")
    print(f"Solver status: {summary['solver_status']} | Termination: {summary['termination_condition']}")
    print(f"Results: {results_dir/'milp_dispatch.csv'}")


if __name__ == "__main__":
    main()
