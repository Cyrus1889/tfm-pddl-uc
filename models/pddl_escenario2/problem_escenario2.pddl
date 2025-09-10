(define (problem despacho_24h_nuevo_escenario)
    (:domain despacho_priorizado)
    (:objects 
        h0 h1 h2 h3 h4 h5 h6 h7 h8 h9 h10 h11 
        h12 h13 h14 h15 h16 h17 h18 h19 h20 h21 h22 h23 
        - hour
    )

    (:init
        ;; --- Configuración inicial (Valores de CSVs) ---
        (= (costo_total) 0)
        (= (costo_pv) 3)
        (= (costo_hidro) 10)
        (= (costo_termica) 250)
        (= (unidad_despacho) 70)  ; Mantenemos granularidad de 70 MW
        (= (presupuesto_hidro_diario) 13000)

        ;; --- Secuencia de tiempo ---
        (hora_actual h0)
        (siguiente h0 h1) (siguiente h1 h2) (siguiente h2 h3) (siguiente h3 h4) (siguiente h4 h5) (siguiente h5 h6)
        (siguiente h6 h7) (siguiente h7 h8) (siguiente h8 h9) (siguiente h9 h10) (siguiente h10 h11) (siguiente h11 h12)
        (siguiente h12 h13) (siguiente h13 h14) (siguiente h14 h15) (siguiente h15 h16) (siguiente h16 h17) (siguiente h17 h18)
        (siguiente h18 h19) (siguiente h19 h20) (siguiente h20 h21) (siguiente h21 h22) (siguiente h22 h23)

        ;; --- Perfiles de Datos (Extraídos y adaptados de los CSV) ---

        ; Perfil de Demanda (demand_profile.csv -)
        (= (demanda h0) 700) (= (demanda h1) 680) (= (demanda h2) 660) (= (demanda h3) 650) (= (demanda h4) 640) (= (demanda h5) 650)
        (= (demanda h6) 680) (= (demanda h7) 720) (= (demanda h8) 780) (= (demanda h9) 820) (= (demanda h10) 840) (= (demanda h11) 850)
        (= (demanda h12) 830) (= (demanda h13) 820) (= (demanda h14) 810) (= (demanda h15) 820) (= (demanda h16) 860) (= (demanda h17) 900)
        (= (demanda h18) 940) (= (demanda h19) 960) (= (demanda h20) 930) (= (demanda h21) 880) (= (demanda h22) 820) (= (demanda h23) 760)

        ; Perfil de Generación PV (pv_profile.csv - redondeado a enteros)
        (= (pv_disponible h0) 0) (= (pv_disponible h1) 0) (= (pv_disponible h2) 0) (= (pv_disponible h3) 0) (= (pv_disponible h4) 0) (= (pv_disponible h5) 0)
        (= (pv_disponible h6) 0) (= (pv_disponible h7) 9) (= (pv_disponible h8) 17) (= (pv_disponible h9) 26) (= (pv_disponible h10) 34) (= (pv_disponible h11) 43)
        (= (pv_disponible h12) 51) (= (pv_disponible h13) 60) (= (pv_disponible h14) 50) (= (pv_disponible h15) 40) (= (pv_disponible h16) 30) (= (pv_disponible h17) 20)
        (= (pv_disponible h18) 10) (= (pv_disponible h19) 0) (= (pv_disponible h20) 0) (= (pv_disponible h21) 0) (= (pv_disponible h22) 0) (= (pv_disponible h23) 0)

        ; Capacidad Hidráulica por Hora (hydro_profile.csv)
        (= (hidro_disponible_hora h0) 600) (= (hidro_disponible_hora h1) 600) (= (hidro_disponible_hora h2) 600) (= (hidro_disponible_hora h3) 600)
        (= (hidro_disponible_hora h4) 600) (= (hidro_disponible_hora h5) 600) (= (hidro_disponible_hora h6) 600) (= (hidro_disponible_hora h7) 600)
        (= (hidro_disponible_hora h8) 600) (= (hidro_disponible_hora h9) 600) (= (hidro_disponible_hora h10) 600) (= (hidro_disponible_hora h11) 600)
        (= (hidro_disponible_hora h12) 600) (= (hidro_disponible_hora h13) 600) (= (hidro_disponible_hora h14) 600) (= (hidro_disponible_hora h15) 600)
        (= (hidro_disponible_hora h16) 600) (= (hidro_disponible_hora h17) 600) (= (hidro_disponible_hora h18) 600) (= (hidro_disponible_hora h19) 600)
        (= (hidro_disponible_hora h20) 600) (= (hidro_disponible_hora h21) 600) (= (hidro_disponible_hora h22) 600) (= (hidro_disponible_hora h23) 600)

        ; Capacidad Térmica por Hora (thermal_profile.csv)
        (= (termica_disponible_hora h0) 700) (= (termica_disponible_hora h1) 700) (= (termica_disponible_hora h2) 700) (= (termica_disponible_hora h3) 700)
        (= (termica_disponible_hora h4) 700) (= (termica_disponible_hora h5) 700) (= (termica_disponible_hora h6) 700) (= (termica_disponible_hora h7) 700)
        (= (termica_disponible_hora h8) 700) (= (termica_disponible_hora h9) 700) (= (termica_disponible_hora h10) 700) (= (termica_disponible_hora h11) 700)
        (= (termica_disponible_hora h12) 700) (= (termica_disponible_hora h13) 700) (= (termica_disponible_hora h14) 700) (= (termica_disponible_hora h15) 700)
        (= (termica_disponible_hora h16) 700) (= (termica_disponible_hora h17) 700) (= (termica_disponible_hora h18) 700) (= (termica_disponible_hora h19) 700)
        (= (termica_disponible_hora h20) 700) (= (termica_disponible_hora h21) 700) (= (termica_disponible_hora h22) 700) (= (termica_disponible_hora h23) 700)
    )

    ;; --- Objetivo ---
    (:goal (and 
        (hora_actual h23)
        (< (demanda h23) (unidad_despacho))
    ))

    ;; --- Métrica a Minimizar ---
    (:metric minimize (costo_total))
)

