import os
import glob
from docx import Document

# 1. STATIC UI DATA (The "Menu" for your Frontend)
# We keep this hardcoded so your Checkboxes and PDF Bullets always look clean/marketing-ready.
PRODUCT_DATA = {
    "Hammer VoiceExplorer": {
        "tagline": "Automated Discovery & Documentation",
        "hard_roi": ["80% reduction in scripting", "Eliminates manual Visio/Excel", "Prevents migration delays"]
    },
    "Hammer Performance": {
        "tagline": "On-Demand Load & Stress Testing",
        "hard_roi": ["Prevents P1 incidents", "Reduces troubleshooting overtime", "Minimizes rollback costs"]
    },
    "Hammer QA": {
        "tagline": "Automated Functional Testing",
        "hard_roi": ["Replaces manual regression", "Runs 20+ parallel tests", "Reduces Defect Escape Ratio"]
    },
    "Ativa Enterprise": {
        "tagline": "End-to-End Voice Network Visibility",
        "hard_roi": ["SLA credit recovery", "Reduces Mean Time to Repair", "Right-sizes SIP trunks"]
    },
    "Hammer VoiceWatch": {
        "tagline": "Active Monitoring (Outside-In)",
        "hard_roi": ["Revenue Protection (Outages)", "Eliminates manual TFN sweeps", "Detects 95% of errors pre-customer"]
    },
    "Hammer Edge": {
        "tagline": "Endpoint Observability (WFH/Remote)",
        "hard_roi": ["Hardware Refresh Savings", "Tier 1 Ticket Deflection", "Reduces Agent Shrinkage"]
    }
}

# 2. DYNAMIC KNOWLEDGE LOADER (The "Brain")
# This reads the .docx files from the /docs folder map them to products.
def load_manuals():
    manuals = {}
    docs_path = os.path.join(os.path.dirname(__file__), 'docs')
    
    # Check if docs folder exists
    if not os.path.exists(docs_path):
        print("WARNING: 'docs' folder not found. Agents will have no memory.")
        return manuals

    # Get all .docx files
    files = glob.glob(os.path.join(docs_path, "*.docx"))
    
    print(f"Loading {len(files)} manuals from {docs_path}...")

    for filepath in files:
        filename = os.path.basename(filepath)
        
        # Simple fuzzy matching to map Filenames -> Product Keys
        # This allows you to name files "Hammer_VoiceWatch_v2.docx" and it still works.
        key = None
        if "VoiceWatch" in filename or "Voicewatch" in filename: key = "Hammer VoiceWatch"
        elif "VoiceExplorer" in filename: key = "Hammer VoiceExplorer"
        elif "Performance" in filename: key = "Hammer Performance"
        elif "QA" in filename: key = "Hammer QA"
        elif "Ativa" in filename: key = "Ativa Enterprise"
        elif "Edge" in filename: key = "Hammer Edge"
        
        if key:
            try:
                doc = Document(filepath)
                full_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
                manuals[key] = full_text
                print(f" -> Loaded memory for: {key}")
            except Exception as e:
                print(f" -> ERROR reading {filename}: {e}")
        else:
            print(f" -> SKIPPED {filename} (Could not match to a Product)")
            
    return manuals

# Load immediately on import
PRODUCT_MANUALS = load_manuals()
