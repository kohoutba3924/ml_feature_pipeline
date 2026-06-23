"""
ACS 5-year variable metadata reference.

This module defines a single ordered mapping:
    RAW_ACS_VARIABLE_NAME → NORMALIZED_SEMANTIC_NAME

This mapping is the *single source of truth* for ACS5 semantics across:
  - ACS5 ingestion (raw variable list = keys)
  - ACS5 normalization (normalized names = values)
  - dbt staging models (column naming + documentation)
  - future feature engineering

Python 3.7+ preserves dict insertion order, so the order in this file
is the canonical order used throughout the pipeline.
"""

ACS5_VARIABLES = {
    # -------------------------
    # Core Demographics
    # -------------------------
    "B01001_001E": "population_total",
    "B01001_002E": "population_male",
    "B01001_026E": "population_female",
    # -------------------------
    # Demographic Breakdown (65+)
    # -------------------------
    "B01001_020E": "male_65_66",
    "B01001_021E": "male_67_69",
    "B01001_022E": "male_70_74",
    "B01001_023E": "male_75_79",
    "B01001_024E": "male_80_84",
    "B01001_025E": "male_85_plus",
    "B01001_044E": "female_65_66",
    "B01001_045E": "female_67_69",
    "B01001_046E": "female_70_74",
    "B01001_047E": "female_75_79",
    "B01001_048E": "female_80_84",
    "B01001_049E": "female_85_plus",
    # -------------------------
    # Under 5
    # -------------------------
    "B01001_003E": "male_under_5",
    "B01001_027E": "female_under_5",
    # -------------------------
    # Median Age
    # -------------------------
    "B01002_001E": "median_age",
    # -------------------------
    # Disability
    # -------------------------
    "B18101H_003E": "disability_under_18",
    "B18101H_006E": "disability_18_64",
    "B18101H_009E": "disability_65_plus",
    # -------------------------
    # Education
    # -------------------------
    "B15003_017E": "edu_high_school",
    "B15003_022E": "edu_bachelors",
    "B15003_023E": "edu_masters",
    "B15003_024E": "edu_professional",
    "B15003_025E": "edu_doctorate",
    # -------------------------
    # Socioeconomic Status
    # -------------------------
    "B17001_001E": "poverty_universe",
    "B17001_002E": "poverty_below",
    "B19013_001E": "median_household_income",
    "B23025_002E": "labor_force",
    "B23025_003E": "labor_force_civilian",
    "B23025_005E": "unemployment_civilian",
    "B25002_001E": "housing_units",
    "B25002_002E": "housing_occupied",
    "B25002_003E": "housing_vacant",
    "B25077_001E": "median_home_value",
    "B25064_001E": "median_gross_rent",
    # -------------------------
    # Minority Status & Language
    # -------------------------
    "B03002_001E": "race_universe",
    "B03002_003E": "race_white",
    "B03002_004E": "race_black",
    "B03002_005E": "race_american_indian",
    "B03002_006E": "race_asian",
    "B03002_007E": "race_pacific_islander",
    "B03002_012E": "race_hispanic",
    "B03002_008E": "race_other",
    "B16004_001E": "language_universe",
    "B16004_022E": "limited_english_5_17",
    "B16004_044E": "limited_english_18_64",
    "B16004_066E": "limited_english_65_plus",
    "B16004_023E": "no_english_5_17",
    "B16004_045E": "no_english_18_64",
    "B16004_067E": "no_english_65_plus",
    # -------------------------
    # Housing & Transportation
    # -------------------------
    "B08201_001E": "vehicle_universe",
    "B08201_002E": "vehicle_none",
    "B25024_001E": "housing_structure_universe",
    "B25024_003E": "housing_1_unit",
    "B25024_004E": "housing_2_unit",
    "B25024_005E": "housing_3_4_unit",
    "B25024_006E": "housing_5_9_unit",
    "B25024_007E": "housing_10_19_unit",
    "B25024_008E": "housing_20_49_unit",
    "B25024_009E": "housing_50_plus_unit",
    "B25024_010E": "housing_mobile_home",
}
