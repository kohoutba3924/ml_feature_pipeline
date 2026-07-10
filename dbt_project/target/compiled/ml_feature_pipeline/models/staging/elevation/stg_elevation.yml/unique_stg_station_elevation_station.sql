
    
    

select
    station as unique_field,
    count(*) as n_records

from "warehouse"."main"."stg_station_elevation"
where station is not null
group by station
having count(*) > 1


