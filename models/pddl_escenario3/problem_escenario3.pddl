(define (problem despacho_24h_escenario_final)
    (:domain despacho_priorizado)
    (:objects
        h0 h1 h2 h3 h4 h5 h6 h7 h8 h9 h10 h11
        h12 h13 h14 h15 h16 h17 h18 h19 h20 h21 h22 h23
        - hour
    )

    (:init
        ;; --- Configuración inicial (Valores de CSVs) ---
        (= (costo_total) 0)
        (= (costo_pv) 0)
        (= (costo_hidro) 10)
        (= (costo_termica) 70)
        (= (unidad_despacho) 1)  ; Granularidad de 1 MW
        (= (presupuesto_hidro_diario) 12000)

        ;; --- Secuencia de tiempo ---
        (hora_actual h0)
        (siguiente h0 h1) (siguiente h1 h2) (siguiente h2 h3) (siguiente h3 h4) (siguiente h4 h5) (siguiente h5 h6)
        (siguiente h6 h7) (siguiente h7 h8) (siguiente h8 h9) (siguiente h9 h10) (siguiente h10 h11) (siguiente h11 h12)
        (siguiente h12 h13) (siguiente h13 h14) (siguiente h14 h15) (siguiente h15 h16) (siguiente h16 h17) (siguiente h17 h18)
        (siguiente h18 h19) (siguiente h19 h20) (siguiente h20 h21) (siguiente h21 h22) (siguiente h22 h23)

        ;; --- Perfiles de Datos (Extraídos y adaptados de los CSV) ---

        ; Perfil de Demanda (demand_profile.csv - redondeado a múltiplos de 40)
        (= (demanda h0) 650) (= (demanda h1) 620) (= (demanda h2) 600) (= (demanda h3) 590) (= (demanda h4) 580) (= (demanda h5) 600)
        (= (demanda h6) 630) (= (demanda h7) 660) (= (demanda h8) 680) (= (demanda h9) 690) (= (demanda h10) 700) (= (demanda h11) 700)
        (= (demanda h12) 690) (= (demanda h13) 680) (= (demanda h14) 670) (= (demanda h15) 680) (= (demanda h16) 700) (= (demanda h17) 740)
        (= (demanda h18) 800) (= (demanda h19) 850) (= (demanda h20) 820) (= (demanda h21) 780) (= (demanda h22) 720) (= (demanda h23) 670)

        ; Perfil de Generación PV (pv_profile.csv)
        (= (pv_disponible h0) 0) (= (pv_disponible h1) 0) (= (pv_disponible h2) 0) (= (pv_disponible h3) 0) (= (pv_disponible h4) 0) (= (pv_disponible h5) 0)
        (= (pv_disponible h6) 20) (= (pv_disponible h7) 70) (= (pv_disponible h8) 150) (= (pv_disponible h9) 230) (= (pv_disponible h10) 280) (= (pv_disponible h11) 295)
        (= (pv_disponible h12) 300) (= (pv_disponible h13) 290) (= (pv_disponible h14) 260) (= (pv_disponible h15) 210) (= (pv_disponible h16) 150) (= (pv_disponible h17) 80)
        (= (pv_disponible h18) 20) (= (pv_disponible h19) 0) (= (pv_disponible h20) 0) (= (pv_disponible h21) 0) (= (pv_disponible h22) 0) (= (pv_disponible h23) 0)

        ; Capacidad Hidráulica por Hora (hydro_profile.csv)
        (= (hidro_disponible_hora h0) 450) (= (hidro_disponible_hora h1) 450) (= (hidro_disponible_hora h2) 450) (= (hidro_disponible_hora h3) 450)
        (= (hidro_disponible_hora h4) 450) (= (hidro_disponible_hora h5) 450) (= (hidro_disponible_hora h6) 450) (= (hidro_disponible_hora h7) 450)
        (= (hidro_disponible_hora h8) 450) (= (hidro_disponible_hora h9) 450) (= (hidro_disponible_hora h10) 450) (= (hidro_disponible_hora h11) 450)
        (= (hidro_disponible_hora h12) 450) (= (hidro_disponible_hora h13) 450) (= (hidro_disponible_hora h14) 450) (= (hidro_disponible_hora h15) 450)
        (= (hidro_disponible_hora h16) 450) (= (hidro_disponible_hora h17) 450) (= (hidro_disponible_hora h18) 450) (= (hidro_disponible_hora h19) 450)
        (= (hidro_disponible_hora h20) 450) (= (hidro_disponible_hora h21) 450) (= (hidro_disponible_hora h22) 450) (= (hidro_disponible_hora h23) 450)

        ; Capacidad Térmica por Hora (thermal_profile.csv)
        (= (termica_disponible_hora h0) 700) (= (termica_disponible_hora h1) 700) (= (termica_disponible_hora h2) 700) (= (termica_disponible_hora h3) 700)
        (= (termica_disponible_hora h4) 700) (= (termica_disponible_hora h5) 700) (= (termica_disponible_hora h6) 700) (= (termica_disponible_hora h7) 700)
        (= (termica_disponible_hora h8) 700) (= (termica_disponible_hora h9) 700) (= (termica_disponible_hora h10) 700) (= (termica_disponible_hora h11) 700)
        (= (termica_disponible_hora h12) 700) (= (termica_disponible_hora h13) 700) (= (termica_disponible_hora h14) 700) (= (termica_disponible_hora h15) 700)
        (= (termica_disponible_hora h16) 700) (= (termica_disponible_hora h17) 700) (= (termica_disponible_hora h18) 700) (= (termica_disponible_hora h19) 700)
        (= (termica_disponible_hora h20) 700) (= (termica_disponible_hora h21) 700) (= (termica_disponible_hora h22) 700) (= (termica_disponible_hora h23) 700)
    )

    (:goal (and
        (hora_actual h23)
        (< (demanda h23) (unidad_despacho))
    ))

    (:metric minimize (costo_total))
)
