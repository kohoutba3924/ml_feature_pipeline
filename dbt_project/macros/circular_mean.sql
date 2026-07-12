{% macro circular_mean(direction_array) %}
    (
        degrees(
            atan2(
                avg(sin(radians({{ direction_array }}))),
                avg(cos(radians({{ direction_array }})))
            )
        )
    )
{% endmacro %}