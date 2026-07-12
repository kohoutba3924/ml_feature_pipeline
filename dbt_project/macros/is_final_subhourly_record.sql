{% macro is_final_subhourly_record(ts, station) %}
    (
        row_number() over (
            partition by {{ station }}, date_trunc('hour', {{ ts }})
            order by {{ ts }} desc
        ) = 1
    )
{% endmacro %}