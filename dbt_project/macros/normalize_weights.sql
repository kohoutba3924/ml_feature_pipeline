{% macro normalize_weight(adjusted_weight, sum_adjusted_weight) %}
    (
        {{ adjusted_weight }}::double /
        nullif({{ sum_adjusted_weight }}, 0)
    )
{% endmacro %}