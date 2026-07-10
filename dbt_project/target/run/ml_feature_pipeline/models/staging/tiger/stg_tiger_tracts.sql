
  
    
    

    create  table
      "warehouse"."main"."stg_tiger_tracts__dbt_tmp"
  
    as (
      with src as (
    select *
    from read_parquet("../data/normalized/tiger_geospatial_tracts.parquet")
)

select
    cast(tract as varchar) as tract,
    cast(state_fips as varchar) as state_fips,
    cast(county_fips as varchar) as county_fips,
    cast(tract_code as varchar) as tract_code,

    cast(centroid_lat as float) as centroid_lat,
    cast(centroid_lon as float) as centroid_lon,

    -- geometry_wkb is already normalized in Python
    geometry_wkb,

    cast(bbox_minx as float) as bbox_minx,
    cast(bbox_miny as float) as bbox_miny,
    cast(bbox_maxx as float) as bbox_maxx,
    cast(bbox_maxy as float) as bbox_maxy

from src
    );
  
  