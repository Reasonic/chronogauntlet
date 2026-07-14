# M5 dispute adjudication — per-case verdicts (HUMAN, single author-rater)

_The auditable record behind the headline **0/42** dispute rate. Sample is seeded/reproducible (seed=42); regenerate the worksheet with `analysis/make_adjudication_sample.py`. Verdict semantics: GENUINE = violates a clause the prompt pins; DISPUTE = a defensible reading; ORACLE-BUG = the reference is wrong. Outcome: **42/42 GENUINE, 0 disputes, 0 oracle bugs** (see M5_ADJUDICATION_RESULT.md). Coverage caveat: single author-rater, concentration-weighted (non-random) sample; a second independent rater on a random subsample is a pre-camera-ready step._

| # | task | family | model | lang | cond/sample | verdict |
|--:|---|---|---|---|---|---|
| 1 | `DSW5_sla_deadline_wall_hours` | dst | claude-haiku-4-5 | python | bare/t0.7_0 | GENUINE |
| 2 | `DSW5_sla_deadline_wall_hours` | dst | claude-haiku-4-5 | python | bare/t0.7_1 | GENUINE |
| 3 | `DSW5_sla_deadline_wall_hours` | dst | claude-opus-4-8 | js | bare/t0.7_0 | GENUINE |
| 4 | `DSW5_sla_deadline_wall_hours` | dst | claude-opus-4-8 | js | bare/t0.7_1 | GENUINE |
| 5 | `C1_elapsed_across_dst` | dst | deepseek-v4-pro | python | mitigation/t0.7_4 | GENUINE |
| 6 | `DSW5_sla_deadline_wall_hours` | dst | deepseek-v4-flash | python | bare/greedy | GENUINE |
| 7 | `DSW5_sla_deadline_wall_hours` | dst | claude-opus-4-8 | js | bare/t0.7_3 | GENUINE |
| 8 | `C2_resolve_gap_forward` | dst | claude-haiku-4-5 | python | mitigation/t0.7_4 | GENUINE |
| 9 | `NAV10_build_local_rolling` | naive_aware | deepseek-v4-flash | python | bare/t0.7_3 | GENUINE |
| 10 | `DSW1_meter_billing_across_dst` | dst | claude-haiku-4-5 | python | bare/t0.7_0 | GENUINE |
| 11 | `D2_weekly_meeting_series` | dst | deepseek-v4-flash | python | mitigation/t0.7_4 | GENUINE |
| 12 | `DSW7_wall_duration_to_real_seconds` | dst | llama-3.3-70b | python | bare/greedy | GENUINE |
| 13 | `D1_offset_in_effect` | dst | claude-haiku-4-5 | python | bare/greedy | GENUINE |
| 14 | `DSW4_overtime_across_25h_day` | dst | claude-haiku-4-5 | python | bare/t0.7_3 | GENUINE |
| 15 | `DSW6_next_k_daily_fires` | dst | claude-haiku-4-5 | python | mitigation/greedy | GENUINE |
| 16 | `D3_classify_wall_time` | dst | claude-haiku-4-5 | python | bare/t0.7_4 | GENUINE |
| 17 | `DSW3_alarm_fire_instants` | dst | claude-haiku-4-5 | python | mitigation/t0.7_1 | GENUINE |
| 18 | `D6_hours_in_local_day` | dst | deepseek-v4-flash | python | bare/t0.7_2 | GENUINE |
| 19 | `F2_add_one_month_clamp` | calendar | llama-3.3-70b | js | mitigation/greedy | GENUINE |
| 20 | `CLW2_add_business_days` | calendar | qwen3.5-9b | js | mitigation/greedy | GENUINE |
| 21 | `F2_add_one_month_clamp` | calendar | llama-3.3-70b | js | mitigation/t0.7_4 | GENUINE |
| 22 | `F3_age_full_years_feb29` | calendar | claude-sonnet-5 | js | bare/t0.7_3 | GENUINE (reclassified from initial DISPUTE — see RESULT.md) |
| 23 | `DSW4_overtime_across_25h_day` | dst | claude-sonnet-5 | python | mitigation/t0.7_1 | GENUINE |
| 24 | `DSW7_wall_duration_to_real_seconds` | dst | claude-haiku-4-5 | python | bare/greedy | GENUINE |
| 25 | `DSW3_alarm_fire_instants` | dst | deepseek-v4-pro | python | mitigation/greedy | GENUINE |
| 26 | `DSW2_distinct_local_days_across_dst` | dst | qwen3.5-9b | python | bare/t0.7_2 | GENUINE |
| 27 | `EPW2_age_whole_days_epoch` | epoch | qwen3.5-9b | js | bare/t0.7_4 | GENUINE |
| 28 | `EPW4_normalize_unit_to_seconds` | epoch | qwen3.5-9b | js | mitigation/t0.7_1 | GENUINE |
| 29 | `D7_nanos_to_epoch_seconds_floor` | epoch | qwen3.5-9b | js | bare/t0.7_1 | GENUINE |
| 30 | `EPW5_iso_duration_seconds` | epoch | qwen3.5-9b | python | bare/t0.7_3 | GENUINE |
| 31 | `A2_to_naive_utc` | naive_aware | qwen3.5-9b | js | bare/greedy | GENUINE |
| 32 | `B3_make_local_from_parts` | naive_aware | claude-haiku-4-5 | python | bare/t0.7_1 | GENUINE |
| 33 | `NAV10_build_local_rolling` | naive_aware | qwen3.5-9b | python | mitigation/greedy | GENUINE |
| 34 | `NAV4_add_business_hours` | naive_aware | claude-haiku-4-5 | python | bare/t0.7_3 | GENUINE |
| 35 | `E7_iso_normalize_offset` | parsing | qwen3.5-9b | python | bare/greedy | GENUINE |
| 36 | `PRW4_duration_hms_truncate` | parsing | deepseek-v4-flash | js | bare/t0.7_1 | GENUINE |
| 37 | `PRW4_duration_hms_truncate` | parsing | deepseek-v4-flash | js | mitigation/t0.7_3 | GENUINE |
| 38 | `PRW4_duration_hms_truncate` | parsing | deepseek-v4-flash | js | bare/t0.7_2 | GENUINE |
| 39 | `TZW3_recurring_daily_to_utc` | tz_conversion | claude-haiku-4-5 | python | bare/t0.7_2 | GENUINE |
| 40 | `B2_meeting_in_zones` | tz_conversion | deepseek-v4-flash | python | bare/greedy | GENUINE |
| 41 | `B2_meeting_in_zones` | tz_conversion | llama-3.3-70b | python | bare/t0.7_1 | GENUINE |
| 42 | `B3_local_to_utc` | tz_conversion | llama-3.3-70b | python | bare/t0.7_0 | GENUINE |

**Totals:** 42/42 GENUINE · 0 DISPUTE · 0 ORACLE-BUG.
