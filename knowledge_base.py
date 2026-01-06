# knowledge_base.py

PRODUCT_DATA = {
    "Hammer VoiceExplorer": {
        "tagline": "Automated Discovery & Documentation",
        "hard_roi": [
            "Reduces Test Automation Development time by 80%.",
            "Eliminates manual documentation hours (Visio/Excel) for legacy IVRs.",
            "Prevents migration delays caused by 'discovery' phases."
        ],
        "soft_roi": [
            "De-risks migrations by creating a 'Digital Twin' of legacy systems.",
            "Visualizes customer journeys for better collaboration.",
            "Identifies 'ghost' menu options and dead ends (Negative Testing)."
        ],
        "metrics": {"savings_factor": 0.80, "category": "Migration"}
    },
    "Hammer Performance": {
        "tagline": "On-Demand Load & Stress Testing",
        "hard_roi": [
            "Prevents costly P1/P2 incidents immediately post-change.",
            "Reduces 'All-Hands' troubleshooting overtime costs.",
            "Minimizes rollback costs by catching defects in staging."
        ],
        "soft_roi": [
            "Validates stability of SIP trunks and SBCs under peak load.",
            "Ensures security patches do not break IVR functionality.",
            "Accelerates digital transformation by providing 'Go-Live' confidence."
        ],
        "metrics": {"savings_factor": 0.40, "category": "Risk"}
    },
    "Hammer QA": {
        "tagline": "Automated Functional Testing for CI/CD",
        "hard_roi": [
            "Replaces manual regression testing labor with automated 'Scenarios'.",
            "Runs 20+ concurrent tests in parallel, slashing testing windows.",
            "Reduces 'Defect Escape Ratio' (cheaper to fix in Dev than Prod)."
        ],
        "soft_roi": [
            "Enables true Agile/DevOps pipelines for Contact Centers.",
            "Validates Omnichannel flows (Voice, Chat, IVA) in one suite.",
            "Reduces QA burnout and 'test fatigue'."
        ],
        "metrics": {"savings_factor": 0.60, "category": "DevOps"}
    },
    "Ativa Enterprise": {
        "tagline": "End-to-End Voice Network Visibility",
        "hard_roi": [
            "Recovers hard dollars via SLA credit enforcement against carriers.",
            "Reduces Mean Time to Repair (MTTR) by automating root-cause isolation.",
            "Right-sizes SBC licenses and SIP trunks (CAPEX Optimization)."
        ],
        "soft_roi": [
            "Proof of innocence: Isolates Carrier vs. Network vs. App faults.",
            "Ensures Voice Quality (MOS) for critical VIP/Executive calls.",
            "Automated alarm suppression reduces NOC alert fatigue."
        ],
        "metrics": {"savings_factor": 0.30, "category": "Ops"}
    },
    "Hammer VoiceWatch": {
        "tagline": "Active Monitoring (Outside-In)",
        "hard_roi": [
            "Revenue Protection: Detects outages minutes before customers do.",
            "Eliminates manual 'sweeps' of TFNs (Labor Savings).",
            "Identifies 90-95% of errors pre-customer impact."
        ],
        "soft_roi": [
            "Verifies global reachability from specific countries.",
            "Validates 'Open/Closed' logic and backend data dips.",
            "Brand Protection: Prevents silent failures on high-visibility lines."
        ],
        "metrics": {"savings_factor": 0.50, "category": "Monitoring"}
    },
    "Hammer Edge": {
        "tagline": "Endpoint Observability (WFH/Remote)",
        "hard_roi": [
            "Hardware Refresh Optimization: Only replace actually failing devices.",
            "Tier 1 Ticket Deflection: Empowers helpdesk to solve WiFi issues.",
            "Reduces shrinkage/downtime for remote agents."
        ],
        "soft_roi": [
            "Visualizes 'Last Mile' issues (ISP vs. Home WiFi).",
            "Protects VDI investments by isolating virtual vs. physical lag.",
            "Non-intrusive monitoring of legacy on-prem PBXs."
        ],
        "metrics": {"savings_factor": 0.25, "category": "Remote"}
    }
}
