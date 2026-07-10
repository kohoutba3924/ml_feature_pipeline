
  
    
    

    create  table
      "warehouse"."main"."stg_tract_elevation__dbt_tmp"
  
    as (
      with src as (
    select *
    from read_parquet("../data/raw/elevation/tract_elevation.parquet")
)

select
    cast(tract as varchar) as tract,

    cast(centroid_lat as float) as centroid_lat,
    cast(centroid_lon as float) as centroid_lon,

    cast(elevation_m as float) as elevation_m

from src
    );
  
  