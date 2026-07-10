
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select station
from "warehouse"."main"."stg_lcdv2_hourly"
where station is null



  
  
      
    ) dbt_internal_test