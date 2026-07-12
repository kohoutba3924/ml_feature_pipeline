{% macro elevation_penalty(elevation_diff_m) %}
    (
        1.0 / (1.0 + ({{ elevation_diff_m }} / 100.0))
    )
{% endmacro %}