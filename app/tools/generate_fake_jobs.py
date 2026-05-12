from __future__ import annotations

import argparse
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

EXPORT_COLUMNS = [
    "title",
    "company_name",
    "location",
    "category",
    "job_type",
    "salary",
    "experience",
    "salary_min",
    "salary_max",
    "url",
    "description",
    "tags",
    "published_at",
]

VIETNAM_LOCATIONS = [
    "Ho Chi Minh City",
    "Hanoi",
    "Da Nang",
    "Hai Phong",
    "Can Tho",
    "Binh Duong",
    "Bac Ninh",
    "Dong Nai",
    "Long An",
    "Hung Yen",
    "Quang Ninh",
    "Thanh Hoa",
    "Nghe An",
    "Hai Duong",
    "Nam Dinh",
    "Thai Nguyen",
    "Vinh Phuc",
    "Hue",
    "Quang Nam",
    "Quang Ngai",
    "Binh Dinh",
    "Phu Yen",
    "Khanh Hoa",
    "Lam Dong",
    "Binh Thuan",
    "Ba Ria - Vung Tau",
    "Tien Giang",
    "Kien Giang",
    "An Giang",
    "Ca Mau",
    "Quy Nhon",
    "Nha Trang",
    "Da Lat",
    "Phan Thiet",
    "Vung Tau",
]

ROLES = [
    ("AI Engineer", "Technology", ["python", "ml", "ai"]),
    ("Backend Engineer", "Technology", ["backend", "api", "python"]),
    ("Frontend Developer", "Technology", ["frontend", "react", "javascript"]),
    ("QA Engineer", "Technology", ["qa", "testing", "automation"]),
    ("DevOps Engineer", "Technology", ["devops", "kubernetes", "cloud"]),
    ("Data Analyst", "Data", ["analytics", "sql", "bi"]),
    ("Data Scientist", "Data", ["python", "ml", "statistics", "sql"]),
    ("Accountant", "Finance", ["accounting", "excel", "tax"]),
    ("Finance Analyst", "Finance", ["finance", "analysis", "reporting"]),
    ("Sales Executive", "Sales", ["sales", "negotiation", "crm"]),
    ("Marketing Specialist", "Marketing", ["marketing", "content", "digital"]),
    ("HR Executive", "Human Resources", ["hr", "recruitment", "onboarding"]),
    ("Customer Service Specialist", "Operations", ["support", "crm", "service"]),
    ("Operations Manager", "Operations", ["operations", "kpi", "process"]),
    ("Logistics Coordinator", "Supply Chain", ["logistics", "warehouse", "supply-chain"]),
    ("Procurement Specialist", "Supply Chain", ["procurement", "sourcing", "vendor"]),
    ("Teacher", "Education", ["teacher", "education", "training"]),
    ("Nurse", "Healthcare", ["nurse", "clinic", "healthcare"]),
    ("Doctor", "Healthcare", ["doctor", "medical", "clinic"]),
    ("Pharmacist", "Healthcare", ["pharmacist", "medicine", "retail"]),
    ("Legal Counsel", "Legal", ["legal", "compliance", "contract"]),
    ("Administrative Officer", "Administration", ["admin", "office", "coordination"]),
    ("Mechanical Engineer", "Engineering", ["mechanical", "autocad", "manufacturing"]),
    ("Content Creator", "Marketing", ["content", "social-media", "creative"]),
]

LINKEDIN_TOPCV_ROLES = [
    ("Sales Executive", "Sales", ["sales", "negotiation", "crm"]),
    ("Business Development Manager", "Sales", ["business-development", "b2b", "pipeline"]),
    ("Marketing Specialist", "Marketing", ["marketing", "campaign", "digital"]),
    ("Data Scientist", "Data", ["python", "ml", "statistics", "sql"]),
    ("PR Executive", "Marketing", ["pr", "communications", "media"]),
    ("HR Executive", "Human Resources", ["hr", "recruitment", "onboarding"]),
    ("Administrative Officer", "Administration", ["admin", "office", "coordination"]),
    ("Legal Counsel", "Legal", ["legal", "compliance", "contract"]),
    ("Accountant", "Finance", ["accounting", "excel", "tax"]),
    ("Auditor", "Finance", ["audit", "risk", "reporting"]),
    ("Real Estate Consultant", "Real Estate", ["real-estate", "sales", "consulting"]),
    ("Construction Supervisor", "Construction", ["construction", "site", "safety"]),
    ("Civil Engineer", "Construction", ["civil", "autocad", "project"]),
    ("Warehouse Operator", "Labor", ["warehouse", "inventory", "forklift"]),
    ("Operations Staff", "Operations", ["operations", "process", "kpi"]),
    ("Customer Service Specialist", "Operations", ["support", "crm", "service"]),
    ("Logistics Coordinator", "Supply Chain", ["logistics", "warehouse", "supply-chain"]),
    ("Procurement Specialist", "Supply Chain", ["procurement", "sourcing", "vendor"]),
]

ITVIEC_TECH_ROLES = [
    ("AI Engineer", "Technology", ["python", "ml", "ai"]),
    ("Backend Engineer", "Technology", ["backend", "api", "python"]),
    ("Frontend Developer", "Technology", ["frontend", "react", "javascript"]),
    ("QA Engineer", "Technology", ["qa", "testing", "automation"]),
    ("DevOps Engineer", "Technology", ["devops", "kubernetes", "cloud"]),
    ("Data Analyst", "Data", ["analytics", "sql", "bi"]),
    ("Data Scientist", "Data", ["python", "ml", "statistics", "sql"]),
    ("Product Manager", "Technology", ["product", "roadmap", "agile"]),
    ("UI UX Designer", "Technology", ["uiux", "figma", "design"]),
]

ITVIEC_NON_TECH_ROLES = [
    ("HR Executive (IT Company)", "Human Resources", ["hr", "it-recruitment", "talent"]),
    ("IT Sales Executive", "Sales", ["it-sales", "saas", "b2b"]),
    ("Content Marketing Executive (Tech)", "Marketing", ["content", "tech", "marketing"]),
]

COMPANY_PREFIX = [
    "VietFuture",
    "NovaLink",
    "GreenTech",
    "Skyline",
    "AnPhat",
    "BlueOcean",
    "PrimeX",
    "MinhLong",
    "Sunrise",
    "GlobalNext",
    "MekongSoft",
    "EastBridge",
    "LotusWave",
    "RedRiver",
    "SaigonPrime",
    "HanoiCore",
    "BlueLotus",
    "VinaSpark",
    "OceanByte",
    "ZenithWorks",
    "AuroraLabs",
    "NexusPoint",
    "FutureScale",
    "RiverStone",
    "NorthStar",
    "SilverMaple",
    "VertexOne",
    "CloudNova",
    "DeltaEdge",
    "VietBridge",
]

IT_COMPANY_SUFFIX = [
    "Tech",
    "Software",
    "Digital",
    "Cloud",
    "Systems",
    "Labs",
    "Solutions",
    "Platform",
    "AI",
    "Data",
]

CORP_COMPANY_SUFFIX = [
    "JSC",
    "Group",
    "Solutions",
    "Vietnam",
    "Corporation",
    "Holdings",
    "Enterprises",
    "Industries",
    "Partners",
    "Global",
]

JOB_TYPES = ["Full-time", "Hybrid", "Remote", "Shift", "Part-time"]
EXPERIENCE_BANDS = ["0-1 nam", "1-3 nam", "2-4 nam", "3-5 nam", "5+ nam"]
LOCATION_SALARY_MULTIPLIER = {
    "Ho Chi Minh City": 1.10,
    "Hanoi": 1.08,
    "Da Nang": 1.00,
    "Hai Phong": 0.95,
    "Can Tho": 0.92,
    "Binh Duong": 0.98,
    "Bac Ninh": 0.96,
    "Dong Nai": 0.95,
    "Long An": 0.94,
    "Hung Yen": 0.95,
    "Quang Ninh": 0.98,
    "Thanh Hoa": 0.92,
    "Nghe An": 0.91,
    "Hai Duong": 0.94,
    "Nam Dinh": 0.90,
    "Thai Nguyen": 0.93,
    "Vinh Phuc": 0.95,
    "Hue": 0.93,
    "Quang Nam": 0.92,
    "Quang Ngai": 0.90,
    "Binh Dinh": 0.92,
    "Phu Yen": 0.90,
    "Khanh Hoa": 0.96,
    "Lam Dong": 0.92,
    "Binh Thuan": 0.91,
    "Ba Ria - Vung Tau": 0.99,
    "Tien Giang": 0.90,
    "Kien Giang": 0.90,
    "An Giang": 0.89,
    "Ca Mau": 0.88,
    "Quy Nhon": 0.92,
    "Nha Trang": 0.96,
    "Da Lat": 0.92,
    "Phan Thiet": 0.91,
    "Vung Tau": 0.99,
}


def _category_salary_table(category: str) -> dict[str, tuple[int, int]]:
    # Unit: million VND/month, calibrated for realistic demo ranges.
    table = {
        "Technology": {
            "0-1 nam": (12, 20),
            "1-3 nam": (18, 32),
            "2-4 nam": (24, 40),
            "3-5 nam": (32, 52),
            "5+ nam": (45, 75),
        },
        "Data": {
            "0-1 nam": (11, 18),
            "1-3 nam": (16, 28),
            "2-4 nam": (22, 36),
            "3-5 nam": (28, 46),
            "5+ nam": (40, 68),
        },
        "Finance": {
            "0-1 nam": (9, 14),
            "1-3 nam": (12, 20),
            "2-4 nam": (16, 26),
            "3-5 nam": (22, 34),
            "5+ nam": (30, 50),
        },
        "Sales": {
            "0-1 nam": (8, 14),
            "1-3 nam": (11, 20),
            "2-4 nam": (15, 26),
            "3-5 nam": (20, 34),
            "5+ nam": (28, 45),
        },
        "Marketing": {
            "0-1 nam": (8, 13),
            "1-3 nam": (11, 18),
            "2-4 nam": (14, 24),
            "3-5 nam": (18, 30),
            "5+ nam": (25, 40),
        },
        "Human Resources": {
            "0-1 nam": (8, 13),
            "1-3 nam": (10, 17),
            "2-4 nam": (13, 22),
            "3-5 nam": (17, 28),
            "5+ nam": (23, 36),
        },
        "Legal": {
            "0-1 nam": (10, 16),
            "1-3 nam": (14, 24),
            "2-4 nam": (18, 30),
            "3-5 nam": (24, 38),
            "5+ nam": (32, 55),
        },
        "Healthcare": {
            "0-1 nam": (9, 15),
            "1-3 nam": (12, 20),
            "2-4 nam": (15, 26),
            "3-5 nam": (20, 34),
            "5+ nam": (28, 45),
        },
        "Operations": {
            "0-1 nam": (8, 13),
            "1-3 nam": (10, 18),
            "2-4 nam": (13, 22),
            "3-5 nam": (17, 28),
            "5+ nam": (23, 38),
        },
        "Supply Chain": {
            "0-1 nam": (8, 14),
            "1-3 nam": (11, 19),
            "2-4 nam": (14, 24),
            "3-5 nam": (19, 30),
            "5+ nam": (25, 40),
        },
        "Construction": {
            "0-1 nam": (9, 15),
            "1-3 nam": (12, 20),
            "2-4 nam": (16, 27),
            "3-5 nam": (21, 34),
            "5+ nam": (28, 45),
        },
        "Real Estate": {
            "0-1 nam": (7, 13),
            "1-3 nam": (10, 18),
            "2-4 nam": (14, 24),
            "3-5 nam": (18, 30),
            "5+ nam": (24, 40),
        },
        "Labor": {
            "0-1 nam": (7, 11),
            "1-3 nam": (8, 14),
            "2-4 nam": (10, 17),
            "3-5 nam": (12, 20),
            "5+ nam": (15, 26),
        },
        "Administration": {
            "0-1 nam": (7, 11),
            "1-3 nam": (9, 14),
            "2-4 nam": (11, 18),
            "3-5 nam": (14, 22),
            "5+ nam": (18, 30),
        },
        "Education": {
            "0-1 nam": (8, 13),
            "1-3 nam": (10, 17),
            "2-4 nam": (12, 22),
            "3-5 nam": (16, 28),
            "5+ nam": (22, 36),
        },
        "Engineering": {
            "0-1 nam": (10, 16),
            "1-3 nam": (14, 24),
            "2-4 nam": (18, 30),
            "3-5 nam": (23, 38),
            "5+ nam": (30, 50),
        },
    }
    return table.get(category, table["Operations"])


def _salary_range(category: str, experience: str, location: str) -> tuple[int, int]:
    base = _category_salary_table(category)
    low, high = base[experience]
    multiplier = LOCATION_SALARY_MULTIPLIER.get(location, 1.0)
    low = max(6, int(round(low * multiplier)))
    high = max(low + 3, int(round(high * multiplier)))
    salary_min = random.randint(low, max(low, high - 4)) * 1_000_000
    salary_max = random.randint(max(salary_min // 1_000_000 + 2, low + 2), high) * 1_000_000
    return salary_min, salary_max


def _roles_for_source(source: str) -> list[tuple[str, str, list[str]]]:
    if source in {"linkedin", "topcv"}:
        return LINKEDIN_TOPCV_ROLES
    if source == "itviec":
        # Keep ITviec mostly technical but still include non-tech in tech companies.
        return ITVIEC_TECH_ROLES * 4 + ITVIEC_NON_TECH_ROLES
    return ROLES


def _build_row(index: int, source: str) -> dict[str, str | int]:
    role, category, tags = random.choice(_roles_for_source(source))
    location = random.choice(VIETNAM_LOCATIONS)
    experience = random.choice(EXPERIENCE_BANDS)
    salary_min, salary_max = _salary_range(category, experience, location)
    if source == "itviec":
        company = f"{random.choice(COMPANY_PREFIX)} {random.choice(IT_COMPANY_SUFFIX)}"
    else:
        company = f"{random.choice(COMPANY_PREFIX)} {random.choice(CORP_COMPANY_SUFFIX)}"
    posted_at = datetime.now() - timedelta(days=random.randint(0, 45), hours=random.randint(0, 23))
    slug = role.lower().replace(" ", "-")
    return {
        "title": role,
        "company_name": company,
        "location": location,
        "category": category,
        "job_type": random.choice(JOB_TYPES),
        "salary": f"{salary_min // 1_000_000}-{salary_max // 1_000_000} trieu VND",
        "experience": experience,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "url": f"https://jobs.local/{source}/{slug}-{index}",
        "description": f"Tuyen dung {role} tai {company} o {location}. Yeu cau kinh nghiem lien quan va ky nang giao tiep tot.",
        "tags": ",".join(tags),
        "published_at": posted_at.isoformat(timespec="seconds") + "+07:00",
    }


def _write_rows(file_path: Path, source: str, rows: int) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=EXPORT_COLUMNS)
        writer.writeheader()
        for idx in range(1, rows + 1):
            writer.writerow(_build_row(idx, source))


def generate_fake_exports(total_rows: int = 900) -> dict[str, int]:
    random.seed(42)
    root = Path(__file__).resolve().parents[2]
    export_dir = root / "legal-imports"

    per_file = max(total_rows // 3, 1)
    plan = {
        "linkedin_jobs.csv": ("linkedin", per_file),
        "itviec_jobs.csv": ("itviec", per_file),
        "topcv_jobs.csv": ("topcv", total_rows - (per_file * 2)),
    }

    result: dict[str, int] = {}
    for filename, (source, rows) in plan.items():
        path = export_dir / filename
        _write_rows(path, source, rows)
        result[filename] = rows
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate fake multi-industry Vietnam job exports.")
    parser.add_argument("--rows", type=int, default=900, help="Total rows to generate across all export files.")
    args = parser.parse_args()

    generated = generate_fake_exports(total_rows=max(args.rows, 3))
    for name, count in generated.items():
        print(f"{name}: {count}")
