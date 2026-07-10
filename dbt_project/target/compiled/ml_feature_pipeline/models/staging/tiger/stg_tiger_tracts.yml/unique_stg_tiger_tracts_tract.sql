
    
    

select
    tract as unique_field,
    count(*) as n_records

from "warehouse"."main"."stg_tiger_tracts"
where tract is not null
group by tract
having count(*) > 1


