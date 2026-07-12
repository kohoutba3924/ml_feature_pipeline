{% macro safe_divide(num, denom) %}
    (
        {{ num }}::double /
        nullif({{ denom }}, 0)
    )
{% endmacro %}