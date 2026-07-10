with src as (
    select *
    from read_parquet("../data/external/lcdv2_stations.parquet")
)

select
    cast(station as varchar) as station,
    cast(name as varchar) as name,

    cast(latitude as float) as latitude,
    cast(longitude as float) as longitude,
    cast(elevation as float) as elevation,

    cast(data_coverage as float) as data_coverage,

    cast(min_date as date) as min_date,
    cast(max_date as date) as max_date

from src
