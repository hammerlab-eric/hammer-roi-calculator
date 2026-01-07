# benchmarks.py

def get_benchmark_profile(industry_input, revenue_input=None):
    """
    Main entry point.
    1. Determines Business Size based on Industry + Revenue.
    2. Returns the specific dictionary of metrics for that profile.
    """
    # 1. Normalize Industry
    industry_key = "Technology" # Default
    if industry_input:
        for key in INDUSTRY_PROFILES.keys():
            if key.lower() in industry_input.lower():
                industry_key = key
                break
    
    # 2. Determine Size
    size = "Medium" # Default
    if revenue_input:
        try:
            rev = float(str(revenue_input).replace(',', '').replace('$', ''))
            thresholds = SIZE_DEFINITIONS.get(industry_key, SIZE_DEFINITIONS["Default"])
            
            if rev < thresholds["Small"]:
                size = "Small"
            elif rev < thresholds["Medium"]:
                size = "Medium"
            else:
                size = "Large"
        except:
            pass # Keep default if parsing fails

    # 3. Retrieve Profile
    profile = INDUSTRY_PROFILES.get(industry_key, {}).get(size, {})
    
    # Fallback to Retail Medium if something goes wrong
    if not profile:
        profile = INDUSTRY_PROFILES["Retail"]["Medium"]
        
    return profile, size, industry_key

# --- REVENUE THRESHOLDS (Upper Limits) ---
SIZE_DEFINITIONS = {
    "Retail":     {"Small": 50_000_000, "Medium": 2_000_000_000},
    "Finance":    {"Small": 25_000_000, "Medium": 500_000_000},
    "Technology": {"Small": 20_000_000, "Medium": 250_000_000},
    "Healthcare": {"Small": 30_000_000, "Medium": 1_000_000_000},
    "Utilities":  {"Small": 40_000_000, "Medium": 1_500_000_000},
    "Insurance":  {"Small": 30_000_000, "Medium": 1_000_000_000},
    "Default":    {"Small": 50_000_000, "Medium": 1_000_000_000}
}

# --- DATASET (From User CSV) ---
INDUSTRY_PROFILES = {
    "Utilities": {
        "Small": {
            "ops": {"avg_cost_per_call": 4.50, "avg_cost_per_transfer": 2.00, "agent_hourly_rate": 22.00, "lost_agent_minutes_per_day": 15, "annual_call_volume": 80000},
            "incidents": {"avg_major_incidents_annually": 2, "avg_mttr_hours": 4.0, "cost_of_downtime_per_hour": 15000, "percent_incidents_preventable": 0.30},
            "cx": {"churn_value_annual": 1500, "churn_rate_tech_related": 0.01, "repeat_call_rate": 0.20, "containment_goal": 0.30, "poor_voice_quality_percent": 0.02},
            "dev": {"avg_projects_annually": 3, "avg_project_delay_days": 5, "dev_hourly_rate": 75.00, "defects_found_in_prod": 5, "cost_to_fix_in_prod": 1500, "manual_test_hours_per_project": 40}
        },
        "Medium": {
            "ops": {"avg_cost_per_call": 5.25, "avg_cost_per_transfer": 2.50, "agent_hourly_rate": 26.00, "lost_agent_minutes_per_day": 18, "annual_call_volume": 600000},
            "incidents": {"avg_major_incidents_annually": 8, "avg_mttr_hours": 5.0, "cost_of_downtime_per_hour": 85000, "percent_incidents_preventable": 0.40},
            "cx": {"churn_value_annual": 4000, "churn_rate_tech_related": 0.01, "repeat_call_rate": 0.22, "containment_goal": 0.40, "poor_voice_quality_percent": 0.03},
            "dev": {"avg_projects_annually": 12, "avg_project_delay_days": 10, "dev_hourly_rate": 85.00, "defects_found_in_prod": 20, "cost_to_fix_in_prod": 2500, "manual_test_hours_per_project": 180}
        },
        "Large": {
            "ops": {"avg_cost_per_call": 6.50, "avg_cost_per_transfer": 3.00, "agent_hourly_rate": 34.00, "lost_agent_minutes_per_day": 22, "annual_call_volume": 5500000},
            "incidents": {"avg_major_incidents_annually": 25, "avg_mttr_hours": 8.0, "cost_of_downtime_per_hour": 450000, "percent_incidents_preventable": 0.50},
            "cx": {"churn_value_annual": 15000, "churn_rate_tech_related": 0.01, "repeat_call_rate": 0.25, "containment_goal": 0.55, "poor_voice_quality_percent": 0.03},
            "dev": {"avg_projects_annually": 60, "avg_project_delay_days": 20, "dev_hourly_rate": 105.00, "defects_found_in_prod": 60, "cost_to_fix_in_prod": 5000, "manual_test_hours_per_project": 600}
        }
    },
    "Retail": {
        "Small": {
            "ops": {"avg_cost_per_call": 3.50, "avg_cost_per_transfer": 1.50, "agent_hourly_rate": 16.00, "lost_agent_minutes_per_day": 12, "annual_call_volume": 250000},
            "incidents": {"avg_major_incidents_annually": 2, "avg_mttr_hours": 2.0, "cost_of_downtime_per_hour": 12000, "percent_incidents_preventable": 0.25},
            "cx": {"churn_value_annual": 500, "churn_rate_tech_related": 0.02, "repeat_call_rate": 0.15, "containment_goal": 0.20, "poor_voice_quality_percent": 0.02},
            "dev": {"avg_projects_annually": 2, "avg_project_delay_days": 3, "dev_hourly_rate": 65.00, "defects_found_in_prod": 4, "cost_to_fix_in_prod": 1000, "manual_test_hours_per_project": 30}
        },
        "Medium": {
            "ops": {"avg_cost_per_call": 4.25, "avg_cost_per_transfer": 1.75, "agent_hourly_rate": 19.00, "lost_agent_minutes_per_day": 16, "annual_call_volume": 4500000},
            "incidents": {"avg_major_incidents_annually": 8, "avg_mttr_hours": 3.5, "cost_of_downtime_per_hour": 120000, "percent_incidents_preventable": 0.35},
            "cx": {"churn_value_annual": 1500, "churn_rate_tech_related": 0.02, "repeat_call_rate": 0.18, "containment_goal": 0.35, "poor_voice_quality_percent": 0.02},
            "dev": {"avg_projects_annually": 15, "avg_project_delay_days": 8, "dev_hourly_rate": 80.00, "defects_found_in_prod": 25, "cost_to_fix_in_prod": 2000, "manual_test_hours_per_project": 120}
        },
        "Large": {
            "ops": {"avg_cost_per_call": 5.00, "avg_cost_per_transfer": 2.25, "agent_hourly_rate": 22.00, "lost_agent_minutes_per_day": 24, "annual_call_volume": 65000000},
            "incidents": {"avg_major_incidents_annually": 45, "avg_mttr_hours": 5.0, "cost_of_downtime_per_hour": 1800000, "percent_incidents_preventable": 0.45},
            "cx": {"churn_value_annual": 4500, "churn_rate_tech_related": 0.02, "repeat_call_rate": 0.22, "containment_goal": 0.50, "poor_voice_quality_percent": 0.03},
            "dev": {"avg_projects_annually": 150, "avg_project_delay_days": 15, "dev_hourly_rate": 95.00, "defects_found_in_prod": 180, "cost_to_fix_in_prod": 3500, "manual_test_hours_per_project": 800}
        }
    },
    "Finance": {
        "Small": {
            "ops": {"avg_cost_per_call": 7.50, "avg_cost_per_transfer": 3.75, "agent_hourly_rate": 26.00, "lost_agent_minutes_per_day": 15, "annual_call_volume": 100000},
            "incidents": {"avg_major_incidents_annually": 3, "avg_mttr_hours": 4.0, "cost_of_downtime_per_hour": 45000, "percent_incidents_preventable": 0.35},
            "cx": {"churn_value_annual": 3500, "churn_rate_tech_related": 0.01, "repeat_call_rate": 0.20, "containment_goal": 0.25, "poor_voice_quality_percent": 0.01},
            "dev": {"avg_projects_annually": 5, "avg_project_delay_days": 7, "dev_hourly_rate": 90.00, "defects_found_in_prod": 6, "cost_to_fix_in_prod": 2500, "manual_test_hours_per_project": 80}
        },
        "Medium": {
            "ops": {"avg_cost_per_call": 9.00, "avg_cost_per_transfer": 4.50, "agent_hourly_rate": 30.00, "lost_agent_minutes_per_day": 20, "annual_call_volume": 2500000},
            "incidents": {"avg_major_incidents_annually": 12, "avg_mttr_hours": 6.0, "cost_of_downtime_per_hour": 350000, "percent_incidents_preventable": 0.45},
            "cx": {"churn_value_annual": 12000, "churn_rate_tech_related": 0.01, "repeat_call_rate": 0.22, "containment_goal": 0.40, "poor_voice_quality_percent": 0.02},
            "dev": {"avg_projects_annually": 25, "avg_project_delay_days": 14, "dev_hourly_rate": 110.00, "defects_found_in_prod": 35, "cost_to_fix_in_prod": 4000, "manual_test_hours_per_project": 300}
        },
        "Large": {
            "ops": {"avg_cost_per_call": 11.50, "avg_cost_per_transfer": 5.75, "agent_hourly_rate": 38.00, "lost_agent_minutes_per_day": 28, "annual_call_volume": 25000000},
            "incidents": {"avg_major_incidents_annually": 60, "avg_mttr_hours": 9.0, "cost_of_downtime_per_hour": 2500000, "percent_incidents_preventable": 0.55},
            "cx": {"churn_value_annual": 35000, "churn_rate_tech_related": 0.01, "repeat_call_rate": 0.25, "containment_goal": 0.55, "poor_voice_quality_percent": 0.02},
            "dev": {"avg_projects_annually": 200, "avg_project_delay_days": 25, "dev_hourly_rate": 135.00, "defects_found_in_prod": 150, "cost_to_fix_in_prod": 6500, "manual_test_hours_per_project": 1200}
        }
    },
    "Healthcare": {
        "Small": {
            "ops": {"avg_cost_per_call": 6.50, "avg_cost_per_transfer": 3.25, "agent_hourly_rate": 25.00, "lost_agent_minutes_per_day": 14, "annual_call_volume": 150000},
            "incidents": {"avg_major_incidents_annually": 3, "avg_mttr_hours": 4.0, "cost_of_downtime_per_hour": 35000, "percent_incidents_preventable": 0.30},
            "cx": {"churn_value_annual": 2500, "churn_rate_tech_related": 0.01, "repeat_call_rate": 0.20, "containment_goal": 0.25, "poor_voice_quality_percent": 0.03},
            "dev": {"avg_projects_annually": 4, "avg_project_delay_days": 6, "dev_hourly_rate": 85.00, "defects_found_in_prod": 5, "cost_to_fix_in_prod": 2000, "manual_test_hours_per_project": 60}
        },
        "Medium": {
            "ops": {"avg_cost_per_call": 8.00, "avg_cost_per_transfer": 4.00, "agent_hourly_rate": 29.00, "lost_agent_minutes_per_day": 18, "annual_call_volume": 3500000},
            "incidents": {"avg_major_incidents_annually": 10, "avg_mttr_hours": 5.5, "cost_of_downtime_per_hour": 250000, "percent_incidents_preventable": 0.40},
            "cx": {"churn_value_annual": 8000, "churn_rate_tech_related": 0.01, "repeat_call_rate": 0.22, "containment_goal": 0.35, "poor_voice_quality_percent": 0.04},
            "dev": {"avg_projects_annually": 20, "avg_project_delay_days": 12, "dev_hourly_rate": 100.00, "defects_found_in_prod": 30, "cost_to_fix_in_prod": 3500, "manual_test_hours_per_project": 250}
        },
        "Large": {
            "ops": {"avg_cost_per_call": 9.50, "avg_cost_per_transfer": 4.75, "agent_hourly_rate": 34.00, "lost_agent_minutes_per_day": 24, "annual_call_volume": 18000000},
            "incidents": {"avg_major_incidents_annually": 40, "avg_mttr_hours": 7.5, "cost_of_downtime_per_hour": 1200000, "percent_incidents_preventable": 0.50},
            "cx": {"churn_value_annual": 20000, "churn_rate_tech_related": 0.01, "repeat_call_rate": 0.25, "containment_goal": 0.45, "poor_voice_quality_percent": 0.05},
            "dev": {"avg_projects_annually": 100, "avg_project_delay_days": 20, "dev_hourly_rate": 125.00, "defects_found_in_prod": 100, "cost_to_fix_in_prod": 5000, "manual_test_hours_per_project": 900}
        }
    },
    "Insurance": {
        "Small": {
            "ops": {"avg_cost_per_call": 6.75, "avg_cost_per_transfer": 3.50, "agent_hourly_rate": 24.00, "lost_agent_minutes_per_day": 15, "annual_call_volume": 120000},
            "incidents": {"avg_major_incidents_annually": 2, "avg_mttr_hours": 4.0, "cost_of_downtime_per_hour": 25000, "percent_incidents_preventable": 0.30},
            "cx": {"churn_value_annual": 3000, "churn_rate_tech_related": 0.01, "repeat_call_rate": 0.18, "containment_goal": 0.25, "poor_voice_quality_percent": 0.02},
            "dev": {"avg_projects_annually": 4, "avg_project_delay_days": 6, "dev_hourly_rate": 85.00, "defects_found_in_prod": 5, "cost_to_fix_in_prod": 2000, "manual_test_hours_per_project": 60}
        },
        "Medium": {
            "ops": {"avg_cost_per_call": 8.25, "avg_cost_per_transfer": 4.25, "agent_hourly_rate": 28.00, "lost_agent_minutes_per_day": 18, "annual_call_volume": 2800000},
            "incidents": {"avg_major_incidents_annually": 9, "avg_mttr_hours": 5.0, "cost_of_downtime_per_hour": 200000, "percent_incidents_preventable": 0.40},
            "cx": {"churn_value_annual": 9000, "churn_rate_tech_related": 0.01, "repeat_call_rate": 0.20, "containment_goal": 0.40, "poor_voice_quality_percent": 0.03},
            "dev": {"avg_projects_annually": 18, "avg_project_delay_days": 12, "dev_hourly_rate": 105.00, "defects_found_in_prod": 28, "cost_to_fix_in_prod": 3500, "manual_test_hours_per_project": 220}
        },
        "Large": {
            "ops": {"avg_cost_per_call": 10.00, "avg_cost_per_transfer": 5.00, "agent_hourly_rate": 33.00, "lost_agent_minutes_per_day": 22, "annual_call_volume": 14000000},
            "incidents": {"avg_major_incidents_annually": 35, "avg_mttr_hours": 7.0, "cost_of_downtime_per_hour": 1100000, "percent_incidents_preventable": 0.50},
            "cx": {"churn_value_annual": 22000, "churn_rate_tech_related": 0.01, "repeat_call_rate": 0.22, "containment_goal": 0.50, "poor_voice_quality_percent": 0.03},
            "dev": {"avg_projects_annually": 90, "avg_project_delay_days": 18, "dev_hourly_rate": 125.00, "defects_found_in_prod": 90, "cost_to_fix_in_prod": 5500, "manual_test_hours_per_project": 850}
        }
    },
    "Technology": {
        "Small": {
            "ops": {"avg_cost_per_call": 5.50, "avg_cost_per_transfer": 2.75, "agent_hourly_rate": 30.00, "lost_agent_minutes_per_day": 12, "annual_call_volume": 80000},
            "incidents": {"avg_major_incidents_annually": 4, "avg_mttr_hours": 3.0, "cost_of_downtime_per_hour": 65000, "percent_incidents_preventable": 0.40},
            "cx": {"churn_value_annual": 4000, "churn_rate_tech_related": 0.03, "repeat_call_rate": 0.15, "containment_goal": 0.45, "poor_voice_quality_percent": 0.01},
            "dev": {"avg_projects_annually": 10, "avg_project_delay_days": 5, "dev_hourly_rate": 110.00, "defects_found_in_prod": 10, "cost_to_fix_in_prod": 2500, "manual_test_hours_per_project": 50}
        },
        "Medium": {
            "ops": {"avg_cost_per_call": 7.00, "avg_cost_per_transfer": 3.50, "agent_hourly_rate": 35.00, "lost_agent_minutes_per_day": 16, "annual_call_volume": 1500000},
            "incidents": {"avg_major_incidents_annually": 15, "avg_mttr_hours": 4.5, "cost_of_downtime_per_hour": 450000, "percent_incidents_preventable": 0.50},
            "cx": {"churn_value_annual": 15000, "churn_rate_tech_related": 0.03, "repeat_call_rate": 0.18, "containment_goal": 0.55, "poor_voice_quality_percent": 0.02},
            "dev": {"avg_projects_annually": 40, "avg_project_delay_days": 10, "dev_hourly_rate": 135.00, "defects_found_in_prod": 45, "cost_to_fix_in_prod": 4500, "manual_test_hours_per_project": 200}
        },
        "Large": {
            "ops": {"avg_cost_per_call": 9.00, "avg_cost_per_transfer": 4.50, "agent_hourly_rate": 42.00, "lost_agent_minutes_per_day": 20, "annual_call_volume": 12000000},
            "incidents": {"avg_major_incidents_annually": 80, "avg_mttr_hours": 6.0, "cost_of_downtime_per_hour": 3500000, "percent_incidents_preventable": 0.60},
            "cx": {"churn_value_annual": 50000, "churn_rate_tech_related": 0.03, "repeat_call_rate": 0.20, "containment_goal": 0.70, "poor_voice_quality_percent": 0.02},
            "dev": {"avg_projects_annually": 300, "avg_project_delay_days": 15, "dev_hourly_rate": 165.00, "defects_found_in_prod": 250, "cost_to_fix_in_prod": 7500, "manual_test_hours_per_project": 1500}
        }
    }
}
