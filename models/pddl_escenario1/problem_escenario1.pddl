(define (problem despacho_24h_escenario_actualizado)
    (:domain despacho_priorizado)
    (:objects 
        h0 h1 h2 h3 h4 h5 h6 h7 h8 h9 h10 h11 
        h12 h13 h14 h15 h16 h17 h18 h19 h20 h21 h22 h23 
        - hour
    )

    (:init
        ;; --- Configuración inicial ---
        (= (costo_total) 0)
        (= (costo_pv) 5)          ; Valor de costs.csv
        (= (costo_hidro) 10)      ; Valor de costs.csv
        (= (costo_termica) 90)    ; Valor de costs.csv
        (= (unidad_despacho) 40)   ; Despachamos en bloques de 40 MWh para mayor precision
        (= (presupuesto_hidro_diario) 9000) ; Valor de system_constraints.csv

        ;; --- Secuencia de tiempo ---
        (hora_actual h0)
        (siguiente h0 h1) (siguiente h1 h2) (siguiente h2 h3) (siguiente h3 h4) (siguiente h4 h5) (siguiente h5 h6)
        (siguiente h6 h7) (siguiente h7 h8) (siguiente h8 h9) (siguiente h9 h10) (siguiente h10 h11) (siguiente h11 h12)
        (siguiente h12 h13) (siguiente h13 h14) (siguiente h14 h15) (siguiente h15 h16) (siguiente h16 h17) (siguiente h17 h18)
        (siguiente h18 h19) (siguiente h19 h20) (siguiente h20 h21) (siguiente h21 h22) (siguiente h22 h23)

        ;; --- Perfiles de Datos (Extraídos de los CSV) ---

        ; Perfil de Demanda (demand_profile.csv)
        (= (demanda h0) 770) (= (demanda h1) 748) (= (demanda h2) 726) (= (demanda h3) 715) (= (demanda h4) 704) (= (demanda h5) 715)
        (= (demanda h6) 748) (= (demanda h7) 792) (= (demanda h8) 858) (= (demanda h9) 902) (= (demanda h10) 924) (= (demanda h11) 935)
        (= (demanda h12) 913) (= (demanda h13) 902) (= (demanda h14) 891) (= (demanda h15) 902) (= (demanda h16) 946) (= (demanda h17) 990)
        (= (demanda h18) 1128) (= (demanda h19) 1152) (= (demanda h20) 1116) (= (demanda h21) 1056) (= (demanda h22) 984) (= (demanda h23) 836)

        ; Perfil de Generación PV (pv_profile.csv)
        (= (pv_disponible h0) 0) (= (pv_disponible h1) 0) (= (pv_disponible h2) 0) (= (pv_disponible h3) 0) (= (pv_disponible h4) 0) (= (pv_disponible h5) 0)
        (= (pv_disponible h6) 0) (= (pv_disponible h7) 2) (= (pv_disponible h8) 4) (= (pv_disponible h9) 6) (= (pv_disponible h10) 8) (= (pv_disponible h11) 10)
        (= (pv_disponible h12) 12) (= (pv_disponible h13) 15) (= (pv_disponible h14) 12) (= (pv_disponible h15) 10) (= (pv_disponible h16) 7) (= (pv_disponible h17) 5)
        (= (pv_disponible h18) 2) (= (pv_disponible h19) 0) (= (pv_disponible h20) 0) (= (pv_disponible h21) 0) (= (pv_disponible h22) 0) (= (pv_disponible h23) 0)

        ; Capacidad Hidráulica por Hora (hydro_profile.csv)
        (= (hidro_disponible_hora h0) 450) (= (hidro_disponible_hora h1) 450) (= (hidro_disponible_hora h2) 450) (= (hidro_disponible_hora h3) 450)
        (= (hidro_disponible_hora h4) 450) (= (hidro_disponible_hora h5) 450) (= (hidro_disponible_hora h6) 450) (= (hidro_disponible_hora h7) 450)
        (= (hidro_disponible_hora h8) 450) (= (hidro_disponible_hora h9) 450) (= (hidro_disponible_hora h10) 450) (= (hidro_disponible_hora h11) 450)
        (= (hidro_disponible_hora h12) 450) (= (hidro_disponible_hora h13) 450) (= (hidro_disponible_hora h14) 450) (= (hidro_disponible_hora h15) 450)
        (= (hidro_disponible_hora h16) 450) (= (hidro_disponible_hora h17) 450) (= (hidro_disponible_hora h18) 450) (= (hidro_disponible_hora h19) 450)
        (= (hidro_disponible_hora h20) 450) (= (hidro_disponible_hora h21) 450) (= (hidro_disponible_hora h22) 450) (= (hidro_disponible_hora h23) 450)

        ; Capacidad Térmica por Hora (thermal_profile.csv - ACTUALIZADO)
        (= (termica_disponible_hora h0) 800) (= (termica_disponible_hora h1) 800) (= (termica_disponible_hora h2) 800) (= (termica_disponible_hora h3) 800)
        (= (termica_disponible_hora h4) 800) (= (termica_disponible_hora h5) 800) (= (termica_disponible_hora h6) 800) (= (termica_disponible_hora h7) 800)
        (= (termica_disponible_hora h8) 800) (= (termica_disponible_hora h9) 800) (= (termica_disponible_hora h10) 800) (= (termica_disponible_hora h11) 800)
        (= (termica_disponible_hora h12) 800) (= (termica_disponible_hora h13) 800) (= (termica_disponible_hora h14) 800) (= (termica_disponible_hora h15) 800)
        (= (termica_disponible_hora h16) 800) (= (termica_disponible_hora h17) 800) (= (termica_disponible_hora h18) 800) (= (termica_disponible_hora h19) 800)
        (= (termica_disponible_hora h20) 800) (= (termica_disponible_hora h21) 800) (= (termica_disponible_hora h22) 800) (= (termica_disponible_hora h23) 800)
    )

    ;; --- Objetivo ---
    (:goal (and 
        ;; El objetivo final es estar en la última hora (h23)...
        (hora_actual h23)
        ;; ...y haber cubierto la demanda de esa última hora.
        (< (demanda h23) (unidad_despacho))
    ))

    ;; --- Métrica a Minimizar ---
    (:metric minimize (costo_total))
)
