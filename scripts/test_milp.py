import pyomo.environ as pyo

# 1. Crear un modelo concreto
model = pyo.ConcreteModel()

# 2. Definir variables de decisión
model.x = pyo.Var(within=pyo.NonNegativeReals)
model.y = pyo.Var(within=pyo.NonNegativeReals)

# 3. Definir la función objetivo
model.objective = pyo.Objective(expr=model.x + 2 * model.y, sense=pyo.maximize)

# 4. Definir restricciones
model.constraint1 = pyo.Constraint(expr=3 * model.x + 4 * model.y <= 12)
model.constraint2 = pyo.Constraint(expr=2 * model.x + model.y <= 6)

# 5. Resolver el modelo
solver = pyo.SolverFactory('glpk', executable = 'C:\\Anaconda3\\envs\\tfm_env\\Library\\bin\\glpsol.exe')
results = solver.solve(model)

# 6. Imprimir resultados
print("--- Resultados de la Optimización ---")
print(f"Estado del solver: {results.solver.status}")
print(f"Condición de terminación: {results.solver.termination_condition}")
if results.solver.termination_condition == pyo.TerminationCondition.optimal:
    print(f"Valor óptimo de la función objetivo = {pyo.value(model.objective)}")
    print(f"Valor de x = {pyo.value(model.x)}")
    print(f"Valor de y = {pyo.value(model.y)}")
else:
    print("No se encontró una solución óptima.")