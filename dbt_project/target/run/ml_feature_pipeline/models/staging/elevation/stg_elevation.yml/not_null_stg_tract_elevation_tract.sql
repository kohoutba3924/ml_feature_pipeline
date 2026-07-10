
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select tract
from "warehouse"."main"."stg_tract_elevation"
where tract is null



  
  
      
    ) dbt_internal_test