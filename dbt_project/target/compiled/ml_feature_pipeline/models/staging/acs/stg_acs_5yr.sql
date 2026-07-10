with src as (
    select *
    from read_parquet('../data/normalized/acs5.parquet')
)

select
    cast(tract as varchar) as tract,
    cast(state as varchar) as state_fips,
    cast(county as varchar) as county_fips,
    cast(tract_code as varchar) as tract_code,

    -- Core Demographics
    cast(population_total as integer) as population_total,
    cast(population_male as integer) as population_male,
    cast(population_female as integer) as population_female,

    -- Demographic Breakdown (65+)
    cast(male_65_66 as integer) as male_65_66,
    cast(male_67_69 as integer) as male_67_69,
    cast(male_70_74 as integer) as male_70_74,
    cast(male_75_79 as integer) as male_75_79,
    cast(male_80_84 as integer) as male_80_84,
    cast(male_85_plus as integer) as male_85_plus,
    cast(female_65_66 as integer) as female_65_66,
    cast(female_67_69 as integer) as female_67_69,
    cast(female_70_74 as integer) as female_70_74,
    cast(female_75_79 as integer) as female_75_79,
    cast(female_80_84 as integer) as female_80_84,
    cast(female_85_plus as integer) as female_85_plus,

    -- Under 5
    cast(male_under_5 as integer) as male_under_5,
    cast(female_under_5 as integer) as female_under_5,

    -- Median Age
    cast(median_age as float) as median_age,

    -- Disability
    cast(disability_under_18 as integer) as disability_under_18,
    cast(disability_18_64 as integer) as disability_18_64,
    cast(disability_65_plus as integer) as disability_65_plus,

    -- Education
    cast(edu_high_school as integer) as edu_high_school,
    cast(edu_bachelors as integer) as edu_bachelors,
    cast(edu_masters as integer) as edu_masters,
    cast(edu_professional as integer) as edu_professional,
    cast(edu_doctorate as integer) as edu_doctorate,

    -- Socioeconomic Status
    cast(poverty_universe as integer) as poverty_universe,
    cast(poverty_below as integer) as poverty_below,
    cast(median_household_income as float) as median_household_income,
    cast(labor_force as integer) as labor_force,
    cast(labor_force_civilian as integer) as labor_force_civilian,
    cast(unemployment_civilian as integer) as unemployment_civilian,
    cast(housing_units as integer) as housing_units,
    cast(housing_occupied as integer) as housing_occupied,
    cast(housing_vacant as integer) as housing_vacant,
    cast(median_home_value as float) as median_home_value,
    cast(median_gross_rent as float) as median_gross_rent,

    -- Minority Status & Language
    cast(race_universe as integer) as race_universe,
    cast(race_white as integer) as race_white,
    cast(race_black as integer) as race_black,
    cast(race_american_indian as integer) as race_american_indian,
    cast(race_asian as integer) as race_asian,
    cast(race_pacific_islander as integer) as race_pacific_islander,
    cast(race_hispanic as integer) as race_hispanic,
    cast(race_other as integer) as race_other,
    cast(language_universe as integer) as language_universe,
    cast(limited_english_5_17 as integer) as limited_english_5_17,
    cast(limited_english_18_64 as integer) as limited_english_18_64,
    cast(limited_english_65_plus as integer) as limited_english_65_plus,
    cast(no_english_5_17 as integer) as no_english_5_17,
    cast(no_english_18_64 as integer) as no_english_18_64,
    cast(no_english_65_plus as integer) as no_english_65_plus,

    -- Housing & Transportation
    cast(vehicle_universe as integer) as vehicle_universe,
    cast(vehicle_none as integer) as vehicle_none,
    cast(housing_structure_universe as integer) as housing_structure_universe,
    cast(housing_1_unit as integer) as housing_1_unit,
    cast(housing_2_unit as integer) as housing_2_unit,
    cast(housing_3_4_unit as integer) as housing_3_4_unit,
    cast(housing_5_9_unit as integer) as housing_5_9_unit,
    cast(housing_10_19_unit as integer) as housing_10_19_unit,
    cast(housing_20_49_unit as integer) as housing_20_49_unit,
    cast(housing_50_plus_unit as integer) as housing_50_plus_unit,
    cast(housing_mobile_home as integer) as housing_mobile_home

from src