
    
    

with child as (
    select station as from_field
    from "warehouse"."main"."stg_lcdv2_hourly"
    where station is not null
),

parent as (
    select station as to_field
    from "warehouse"."main"."stg_lcdv2_station"
)

select
    from_field

from child
left join parent
    on child.from_field = parent.to_field

where parent.to_field is null


