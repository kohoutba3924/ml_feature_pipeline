with src as (
    select *
    from read_parquet("../data/normalized/lcdv2/")
)

select
    cast(station as varchar) as station,
    cast(timestamp as timestamp) as timestamp,

    -- Temperature: °C (tenths) → °F
    ((cast(dry_bulb_temp as float) / 10.0) * 9.0/5.0 + 32.0) as dry_bulb_temp,
    ((cast(wet_bulb_temp as float) / 10.0) * 9.0/5.0 + 32.0) as wet_bulb_temp,
    ((cast(dew_point_temp as float) / 10.0) * 9.0/5.0 + 32.0) as dew_point_temp,

    cast(relative_humidity as float) as relative_humidity,

    -- Wind: m/s (tenths) → mph
    ((cast(wind_speed as float) / 10.0) * 2.236936) as wind_speed,
    cast(wind_direction as float) as wind_direction,
    ((cast(wind_gust_speed as float) / 10.0) * 2.236936) as wind_gust_speed,

    -- Precipitation: mm (tenths) → inches
    ((cast(precipitation as float) / 10.0) * 0.0393701) as precipitation,

    -- Visibility: km (thousandths) → miles
    ((cast(visibility as float) / 1000.0) * 0.621371) as visibility,

    -- Pressure: hPa (tenths) → inHg
    ((cast(station_pressure as float) / 10.0) * 0.0295299830714) as station_pressure,
    ((cast(barometric_pressure as float) / 10.0) * 0.0295299830714) as barometric_pressure

from src