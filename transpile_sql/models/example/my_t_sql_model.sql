SELECT TOP 10 *
from {{ ref('my_first_dbt_model') }}
WHERE
  id = 1
