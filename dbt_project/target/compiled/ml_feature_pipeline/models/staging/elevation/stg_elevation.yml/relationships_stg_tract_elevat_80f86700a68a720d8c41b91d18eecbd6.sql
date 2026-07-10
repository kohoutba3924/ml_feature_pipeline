
    
    

with child as (
    select tract as from_field
    from "warehouse"."main"."stg_tract_elevation"
    where tract is not null
),

parent as (
    select tract as to_field
    from "warehouse"."main"."stg_tiger_tracts"
)

select
    from_field

from child
left join parent
    on child.from_field = parent.to_field

where parent.to_field is null


