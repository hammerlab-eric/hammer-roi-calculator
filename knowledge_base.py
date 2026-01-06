# knowledge_base.py

# 1. STATIC PRODUCT DATA (Fallbacks & General Info)
PRODUCT_DATA = {
    "Hammer VoiceExplorer": {
        "tagline": "Automated Discovery & Documentation",
        "hard_roi": [
            "Reduces Test Automation Development time by 80%.",
            "Eliminates manual documentation hours (Visio/Excel).",
            "Prevents migration delays caused by 'discovery' phases."
        ],
        "soft_roi": "Accelerates cloud migration by creating a 'Digital Twin' of legacy systems.",
        "math_variables": {
            "scenario_title": "Migration Discovery Efficiency",
            "metric_unit": "Engineer Hours/Year",
            "cost_per_unit_label": "Avg. DevOps Hourly Rate",
            "cost_per_unit_value": 85,
            "before_label": "Manual Documentation",
            "before_qty": 1200,
            "after_label": "Automated Discovery",
            "after_qty": 200
        }
    },
    "Hammer Performance": {
        "tagline": "On-Demand Load & Stress Testing",
        "hard_roi": [
            "Prevents costly P1/P2 incidents post-change.",
            "Reduces 'All-Hands' troubleshooting overtime.",
            "Minimizes rollback costs by catching defects in staging."
        ],
        "soft_roi": "Validates stability of SIP trunks and SBCs under peak load.",
        "math_variables": {
            "scenario_title": "Peak Traffic Outage Avoidance",
            "metric_unit": "Hours of Critical Downtime/Year",
            "cost_per_unit_label": "Revenue Risk per Hour",
            "cost_per_unit_value": 45000,
            "before_label": "Unverified Capacity",
            "before_qty": 8,
            "after_label": "Load-Tested Capacity",
            "after_qty": 0.5
        }
    },
    "Hammer QA": {
        "tagline": "Automated Functional Testing",
        "hard_roi": [
            "Replaces manual regression testing labor.",
            "Runs 20+ concurrent tests in parallel.",
            "Reduces 'Defect Escape Ratio' to Production."
        ],
        "soft_roi": "Enables true Agile/DevOps pipelines for Contact Centers.",
        "math_variables": {
            "scenario_title": "Regression Testing Automation",
            "metric_unit": "QA Testing Hours/Year",
            "cost_per_unit_label": "QA Analyst Hourly Rate",
            "cost_per_unit_value": 60,
            "before_label": "Manual Dialing",
            "before_qty": 2500,
            "after_label": "Automated Scenarios",
            "after_qty": 250
        }
    },
    "Ativa Enterprise": {
        "tagline": "End-to-End Voice Network Visibility",
        "hard_roi": [
            "Recovers hard dollars via SLA credit enforcement.",
            "Reduces Mean Time to Repair (MTTR).",
            "Right-sizes SBC licenses and SIP trunks."
        ],
        "soft_roi": "Isolates Carrier vs. Network vs. App faults instantly.",
        "math_variables": {
            "scenario_title": "MTTR Reduction (Ops)",
            "metric_unit": "Hours spent Troubleshooting/Year",
            "cost_per_unit_label": "Senior Engineer Hourly Rate",
            "cost_per_unit_value": 110,
            "before_label": "Manual Packet Analysis",
            "before_qty": 800,
            "after_label": "Automated Root Cause",
            "after_qty": 150
        }
    },
    "Hammer VoiceWatch": {
        "tagline": "Active Monitoring (Outside-In)",
        "hard_roi": [
            "Revenue Protection: Detects outages early.",
            "Eliminates manual 'sweeps' of TFNs.",
            "Identifies 90-95% of errors pre-customer impact."
        ],
        "soft_roi": "Verifies global reachability from specific countries.",
        "math_variables": {
            "scenario_title": "Toll-Free Number (TFN) Audits",
            "metric_unit": "Hours spent Testing TFNs/Year",
            "cost_per_unit_label": "Operational Hourly Cost",
            "cost_per_unit_value": 55,
            "before_label": "Manual Morning Sweeps",
            "before_qty": 1000,
            "after_label": "Automated Monitoring",
            "after_qty": 0
        }
    },
    "Hammer Edge": {
        "tagline": "Endpoint Observability (WFH/Remote)",
        "hard_roi": [
            "Hardware Refresh Optimization.",
            "Tier 1 Ticket Deflection.",
            "Reduces shrinkage/downtime for remote agents."
        ],
        "soft_roi": "Visualizes 'Last Mile' issues (ISP vs. Home WiFi).",
        "math_variables": {
            "scenario_title": "Remote Agent Troubleshooting",
            "metric_unit": "Helpdesk Tickets/Year",
            "cost_per_unit_label": "Cost per Ticket (L1)",
            "cost_per_unit_value": 25,
            "before_label": "Blind Troubleshooting",
            "before_qty": 5000,
            "after_label": "Edge Diagnostic Data",
            "after_qty": 2500
        }
    }
}

# 2. AGENT "MENU" (The Brain Logic)
# These map specific user problems to the correct math model.
ROI_ARCHETYPES = {
    "Hammer VoiceWatch": {
        "outage_avoidance": {
            "title": "Cost of Downtime (Revenue Protection)",
            "logic": "Detects outages early -> Reduces Downtime Minutes -> Saves Revenue.",
            [cite_start]"source_doc": "VoiceWatch ROI: 'Cost of Downtime Avoided' & 'Revenue Protection' [cite: 236]"
        },
        "labor_savings": {
            "title": "Operational Efficiency (Manual Testing)",
            "logic": "Automates manual TFN sweeps -> Reduces FTE Hours -> Saves Labor Cost.",
            [cite_start]"source_doc": "VoiceWatch ROI: 'Testing Efficiency (Labor Savings)' [cite: 243]"
        },
        "mttr_reduction": {
            "title": "Mean Time to Repair (MTTR)",
            "logic": "Pinpoints root cause (Carrier vs Internal) -> Faster Fixes -> Lower Support Costs.",
            [cite_start]"source_doc": "VoiceWatch ROI: 'Mean Time to Repair' [cite: 246]"
        }
    },
    "Hammer QA": {
        "defect_escape": {
            "title": "Defect Escape Ratio (Risk)",
            "logic": "Catches bugs in Dev -> Prevents Prod Defects -> Avoids Emergency Fix Costs.",
            [cite_start]"source_doc": "Hammer QA: 'Defect Escape Ratio' [cite: 93]"
        },
        "regression_speed": {
            "title": "Regression Testing Velocity",
            "logic": "Parallel execution -> Reduces Cycle Time -> Increases Release Velocity.",
            [cite_start]"source_doc": "Hammer QA: 'Accelerated Scenarios' [cite: 125]"
        }
    },
    "Hammer VoiceExplorer": {
        "migration_speed": {
            "title": "Migration De-Risking (Discovery)",
            "logic": "Automated discovery -> Prevents 'Discovery Phase' delays -> Faster Cloud Migration.",
            [cite_start]"source_doc": "VoiceExplorer: 'Migration Readiness' [cite: 147]"
        },
        "doc_labor": {
            "title": "Documentation Labor Savings",
            "logic": "Automated mapping -> Replaces manual Visio/Excel work -> Saves Engineer Hours.",
            [cite_start]"source_doc": "VoiceExplorer: 'Documentation Effort Reduction' [cite: 184]"
        }
    },
    "Hammer Performance": {
        "outage_risk": {
            "title": "Peak Traffic Stability",
            "logic": "Stress tests pre-go-live -> Prevents crashes -> Avoids Revenue Loss.",
            [cite_start]"source_doc": "Hammer Performance: 'Downtime Cost Avoidance' [cite: 90]"
        },
        "troubleshooting": {
            "title": "War Room Avoidance",
            "logic": "Proactive testing -> Fewer P1 Incidents -> Less Overtime/All-Hands calls.",
            [cite_start]"source_doc": "Hammer Performance: 'Labor Savings (Troubleshooting)' [cite: 100]"
        }
    },
    "Ativa Enterprise": {
        "sla_credits": {
            "title": "Vendor Accountability (SLA Recovery)",
            "logic": "Monitors Carrier SLAs -> Proves violations -> Recovers Cash Credits.",
            [cite_start]"source_doc": "Ativa ROI: 'SLA Credit Recovery' [cite: 286]"
        },
        "mttr_innocence": {
            "title": "Mean Time to Innocence",
            "logic": "Isolates Network vs App faults -> Stops Finger-pointing -> Saves Eng. Hours.",
            [cite_start]"source_doc": "Ativa ROI: 'Mean Time to Innocence' [cite: 297]"
        }
    },
    "Hammer Edge": {
        "hardware_refresh": {
            "title": "Hardware Refresh Optimization",
            "logic": "Identifies actual PC health -> Prevents blanket PC replacements -> Saves CAPEX.",
            [cite_start]"source_doc": "Hammer Edge: 'Hardware Refresh Optimization' [cite: 33]"
        },
        "ticket_deflection": {
            "title": "Tier 1 Ticket Deflection",
            "logic": "Self-healing/diagnosis -> Resolves WiFi issues at L1 -> Avoids L2/L3 escalation.",
            [cite_start]"source_doc": "Hammer Edge: 'Tier 1 Ticket Deflection' [cite: 37]"
        }
    }
}
