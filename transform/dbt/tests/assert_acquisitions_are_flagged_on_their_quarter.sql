-- Every acquisition falls on a bank-quarter row and is flagged there, with the materiality
-- the event record gives it. A join that dropped or duplicated an event would let a beta
-- spanning an acquisition read as a clean one on the bank explorer. An acquisition in a
-- quarter where neither a cost nor a balance resolves fails here too, since its step could
-- not have been measured either.

select
    events.cik,
    events.event_quarter,
    events.event_type,
    events.material,
    quarters.event_type as flagged_type,
    quarters.material_event
from {{ ref('bank_entity_events') }} as events
left join {{ ref('fct_bank_quarter') }} as quarters
  on quarters.cik = events.cik
 and quarters.quarter_end = events.event_quarter
where events.event_type in ('acquisition', 'reverse_acquisition')
  and (
      quarters.cik is null
      or quarters.event_type is distinct from events.event_type
      or quarters.material_event <> events.material
  )
