with src as (
    select *
    from read_parquet("../data/raw/elevation/station_elevation.parquet")
)

select
    cast(station as varchar) as station,

    cast(latitude as float) as latitude,
    cast(longitude as float) as longitude,

    cast(elevation_m as float) as elevation_m

from src
