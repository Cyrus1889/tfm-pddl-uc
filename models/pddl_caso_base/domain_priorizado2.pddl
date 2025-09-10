(define (domain despacho_priorizado)
    (:requirements :typing :fluents)
    (:types hour)

    (:predicates 
        (hora_actual ?h - hour)
        (pv_agotado ?h - hour)
        (hidro_agotado ?h - hour)
        (siguiente ?h1 ?h2 - hour)
    )

    (:functions
        (demanda ?h - hour)
        (pv_disponible ?h - hour)
        (hidro_disponible_hora ?h - hour)
        (termica_disponible_hora ?h - hour)
        ;; --- LÍNEA ELIMINADA ---
        ; (presupuesto_hidro_diario)

        (costo_pv)
        (costo_hidro)
        (costo_termica)
        (costo_total)
        (unidad_despacho)
    )

    ;; ... (acciones de PV no cambian) ...

    (:action despachar_pv
        :parameters (?h - hour)
        :precondition (and
            (hora_actual ?h)
            (not (pv_agotado ?h))
            (>= (demanda ?h) (unidad_despacho))
            (>= (pv_disponible ?h) (unidad_despacho))
        )
        :effect (and
            (decrease (demanda ?h) (unidad_despacho))
            (decrease (pv_disponible ?h) (unidad_despacho))
            (increase (costo_total) (* (unidad_despacho) (costo_pv)))
        )
    )

    (:action marcar_pv_agotado
        :parameters (?h - hour)
        :precondition (and
            (hora_actual ?h)
            (not (pv_agotado ?h))
            (or
                (< (pv_disponible ?h) (unidad_despacho))
                (< (demanda ?h) (unidad_despacho))
            )
        )
        :effect (pv_agotado ?h)
    )
    
    ;; --- ACCIONES HIDROELÉCTRICAS CORREGIDAS ---

    (:action despachar_hidro
        :parameters (?h - hour)
        :precondition (and
            (hora_actual ?h)
            (pv_agotado ?h)
            (not (hidro_agotado ?h))
            (>= (demanda ?h) (unidad_despacho))
            (>= (hidro_disponible_hora ?h) (unidad_despacho))
            ;; --- LÍNEA ELIMINADA ---
            ; (>= (presupuesto_hidro_diario) (unidad_despacho))
        )
        :effect (and
            (decrease (demanda ?h) (unidad_despacho))
            (decrease (hidro_disponible_hora ?h) (unidad_despacho))
            ;; --- LÍNEA ELIMINADA ---
            ; (decrease (presupuesto_hidro_diario) (unidad_despacho))
            (increase (costo_total) (* (unidad_despacho) (costo_hidro)))
        )
    )

    (:action marcar_hidro_agotado
        :parameters (?h - hour)
        :precondition (and
            (hora_actual ?h)
            (pv_agotado ?h)
            (not (hidro_agotado ?h))
            (or
                (< (hidro_disponible_hora ?h) (unidad_despacho))
                ;; --- LÍNEA ELIMINADA ---
                ; (< (presupuesto_hidro_diario) (unidad_despacho))
                (< (demanda ?h) (unidad_despacho))
            )
        )
        :effect (hidro_agotado ?h)
    )

    ;; ... (acciones de TÉRMICA y AVANZAR_HORA no cambian) ...

    (:action despachar_termica
        :parameters (?h - hour)
        :precondition (and
            (hora_actual ?h)
            (pv_agotado ?h)
            (hidro_agotado ?h)
            (>= (demanda ?h) (unidad_despacho))
            (>= (termica_disponible_hora ?h) (unidad_despacho))
        )
        :effect (and
            (decrease (demanda ?h) (unidad_despacho))
            (decrease (termica_disponible_hora ?h) (unidad_despacho))
            (increase (costo_total) (* (unidad_despacho) (costo_termica)))
        )
    )
    
    (:action avanzar_hora
        :parameters (?h_actual ?h_siguiente - hour)
        :precondition (and
            (hora_actual ?h_actual)
            (siguiente ?h_actual ?h_siguiente)
            (or
                (< (demanda ?h_actual) (unidad_despacho))
                (and 
                    (pv_agotado ?h_actual) 
                    (hidro_agotado ?h_actual) 
                    (< (termica_disponible_hora ?h_actual) (unidad_despacho))
                )
            )
        )
        :effect (and
            (not (hora_actual ?h_actual))
            (hora_actual ?h_siguiente)
        )
    )
)
