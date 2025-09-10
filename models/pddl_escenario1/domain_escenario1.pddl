(define (domain despacho_priorizado)
    (:requirements :typing :fluents)
    (:types hour)

    ;; ----------------------------------------------------
    ;; PREDICADOS: Estados y compuertas de control
    ;; ----------------------------------------------------
    (:predicates 
        (hora_actual ?h - hour)

        ;; Compuertas de prioridad: Se activan cuando una fuente se agota en una hora.
        (pv_agotado ?h - hour)
        (hidro_agotado ?h - hour)

        ;; Secuencia de tiempo
        (siguiente ?h1 ?h2 - hour)
    )

    ;; ----------------------------------------------------
    ;; FUNCIONES: Valores numéricos que cambian
    ;; ----------------------------------------------------
    (:functions
        (demanda ?h - hour)                 ; La demanda restante en una hora.

        ;; Energía disponible
        (pv_disponible ?h - hour)           ; PV disponible en la hora.
        (hidro_disponible_hora ?h - hour)   ; Límite de generación hidroeléctrica en la hora.
        (termica_disponible_hora ?h - hour); Límite de generación térmica en la hora.
        (presupuesto_hidro_diario)          ; Límite de energía hidroeléctrica para todo el día.

        ;; Costos y configuración
        (costo_pv)
        (costo_hidro)
        (costo_termica)
        (costo_total)                       ; El valor que queremos minimizar.
        (unidad_despacho)                   ; La cantidad fija de MWh a despachar en cada paso.
    )

    ;; =================================================================================
    ;; ACCIONES DE PRIORIDAD (COMPUERTAS)
    ;; =================================================================================
    
    ;; Activa la compuerta 'pv_agotado' si la energía PV disponible es menor que una unidad.
    (:action activar_flag_pv_agotado
        :parameters (?h - hour)
        :precondition (and 
            (hora_actual ?h)
            (not (pv_agotado ?h))
            (< (pv_disponible ?h) (unidad_despacho))
        )
        :effect (and 
            (pv_agotado ?h)
        )
    )
    
    ;; Activa la compuerta 'hidro_agotado' si el presupuesto diario o la capacidad por hora es menor que una unidad.
    (:action activar_flag_hidro_agotado
        :parameters (?h - hour)
        :precondition (and
            (hora_actual ?h)
            (not (hidro_agotado ?h))
            ;; Se agota si no queda presupuesto o si ya no se puede generar en esta hora.
            (or
                (< (presupuesto_hidro_diario) (unidad_despacho))
                (< (hidro_disponible_hora ?h) (unidad_despacho))
            )
        )
        :effect (and 
            (hidro_agotado ?h)
        )
    )

    ;; =================================================================================
    ;; ACCIONES DE DESPACHO DE ENERGÍA
    ;; =================================================================================

    ;; Despacha una unidad de energía solar (PV), la más barata.
    (:action despachar_pv
        :parameters (?h - hour)
        :precondition (and
            (hora_actual ?h)
            (>= (demanda ?h) (unidad_despacho))
            (>= (pv_disponible ?h) (unidad_despacho))
        )
        :effect (and
            (decrease (demanda ?h) (unidad_despacho))
            (decrease (pv_disponible ?h) (unidad_despacho))
            (increase (costo_total) (* (unidad_despacho) (costo_pv)))
        )
    )

    ;; Despacha una unidad de energía hidroeléctrica.
    (:action despachar_hidro
        :parameters (?h - hour)
        :precondition (and
            (hora_actual ?h)
            (pv_agotado ?h) ; Requiere que la compuerta PV esté abierta.
            (>= (demanda ?h) (unidad_despacho))
            (>= (hidro_disponible_hora ?h) (unidad_despacho))
            (>= (presupuesto_hidro_diario) (unidad_despacho))
        )
        :effect (and
            (decrease (demanda ?h) (unidad_despacho))
            (decrease (hidro_disponible_hora ?h) (unidad_despacho))
            (decrease (presupuesto_hidro_diario) (unidad_despacho))
            (increase (costo_total) (* (unidad_despacho) (costo_hidro)))
        )
    )

    ;; Despacha una unidad de energía térmica, la más cara.
    (:action despachar_termica
        :parameters (?h - hour)
        :precondition (and
            (hora_actual ?h)
            (pv_agotado ?h)   ; Requiere que la compuerta PV esté abierta.
            (hidro_agotado ?h)   ; Requiere que la compuerta Hidro esté abierta.
            (>= (demanda ?h) (unidad_despacho))
            (>= (termica_disponible_hora ?h) (unidad_despacho))
        )
        :effect (and
            (decrease (demanda ?h) (unidad_despacho))
            (decrease (termica_disponible_hora ?h) (unidad_despacho))
            (increase (costo_total) (* (unidad_despacho) (costo_termica)))
        )
    )
    
    ;; =================================================================================
    ;; ACCIÓN DE CONTROL DE TIEMPO
    ;; =================================================================================
    
    ;; Avanza a la siguiente hora.
    (:action avanzar_hora
        :parameters (?h_actual ?h_siguiente - hour)
        :precondition (and
            (hora_actual ?h_actual)
            (siguiente ?h_actual ?h_siguiente)
            ;; Solo se puede avanzar si la demanda ya fue cubierta...
            (or
                (< (demanda ?h_actual) (unidad_despacho))
                ;; ...o si ya no queda energía de ningún tipo para despachar.
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
