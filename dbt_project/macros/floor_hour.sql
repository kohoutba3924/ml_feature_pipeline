{% macro floor_hour(ts) %}
    date_trunc('hour', {{ ts }})
{% endmacro %}